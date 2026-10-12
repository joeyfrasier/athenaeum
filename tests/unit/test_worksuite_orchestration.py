"""Overlapping Temporal calls keep synthetic tenant repositories isolated."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from worksuite_agent.orchestration import run_workflow
from worksuite_agent.repository import InMemoryConfigurationRepository


class TemporalRepositoryOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlapping_runs_keep_ownership_after_the_first_run_finishes(self):
        workers = {}
        executions = []
        started = [asyncio.Event(), asyncio.Event()]
        proceed = [asyncio.Event(), asyncio.Event()]

        class SyntheticWorker:
            def __init__(self, client, *, task_queue, workflows, activities):
                self.queue = task_queue
                self.activities = {activity.__name__: activity for activity in activities}

            async def __aenter__(self):
                workers[self.queue] = self
                return self

            async def __aexit__(self, *error):
                if workers.get(self.queue) is self:
                    del workers[self.queue]

        class SyntheticClient:
            async def execute_workflow(self, workflow, tenant_id, *, id, task_queue):
                index = len(executions)
                executions.append({"id": id, "queue": task_queue})
                started[index].set()
                await proceed[index].wait()
                # Route to the registered worker as Temporal would, then execute
                # the real activities, repository, models, and diagram builder.
                registered = workers[task_queue].activities
                configuration = await registered["load_configuration_activity"](tenant_id)
                return await registered["build_mermaid_diagrams_activity"](configuration)

        def repository(tenant_id, name):
            return InMemoryConfigurationRepository(
                {"tenants": [{"tenant_id": tenant_id, "name": name}]}
            )

        with patch("worksuite_agent.orchestration.Client.connect", AsyncMock(return_value=SyntheticClient())), patch(
            "worksuite_agent.orchestration.Worker", SyntheticWorker
        ):
            first = asyncio.create_task(run_workflow("synthetic:7233", "tenant-alpha", repository("tenant-alpha", "Alpha Export")))
            await asyncio.wait_for(started[0].wait(), timeout=2)
            second = asyncio.create_task(run_workflow("synthetic:7233", "tenant-beta", repository("tenant-beta", "Beta Export")))
            await asyncio.wait_for(started[1].wait(), timeout=2)
            proceed[0].set()
            first_result = (await asyncio.gather(first, return_exceptions=True))[0]
            # The second call loads its export only after the first call's
            # Worker exit and run_workflow cleanup have finished.
            proceed[1].set()
            second_result = (await asyncio.gather(second, return_exceptions=True))[0]

        with self.subTest(run="first_export_ownership"):
            self.assertIsInstance(first_result, dict)
            self.assertIn("Alpha Export", first_result["module_overview"])
            self.assertNotIn("Beta Export", first_result["module_overview"])
        with self.subTest(run="second_survives_first_completion"):
            self.assertIsInstance(second_result, dict)
            self.assertIn("Beta Export", second_result["module_overview"])
            self.assertNotIn("Alpha Export", second_result["module_overview"])
        with self.subTest(run="independent_worker_routes"):
            self.assertNotEqual(executions[0]["queue"], executions[1]["queue"])
            self.assertTrue(all(run["queue"].startswith("worksuite-assistant-") for run in executions))
            self.assertNotEqual(executions[0]["id"], executions[1]["id"])
        self.assertFalse(workers)


if __name__ == "__main__":
    unittest.main()
