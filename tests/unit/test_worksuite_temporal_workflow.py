"""Exercise workflow orchestration without connecting to a Temporal server."""

from datetime import timedelta
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from temporalio.api.failure.v1 import Failure
from temporalio.converter import DataConverter

from worksuite_agent.repository import ConfigurationRepository, InMemoryConfigurationRepository
from worksuite_agent.temporal_activities import (
    ConfigurationActivities,
    build_mermaid_diagrams_activity,
)
from worksuite_agent.temporal_workflows import GenerateTenantDiagramWorkflow


class TenantDiagramWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_input_errors_match_sdk_converted_non_retryable_types(self):
        for error_type, tables in (
            (ValueError, {}),
            (KeyError, {"tenants": [{}]}),
            (ValidationError, {"tenants": [{"tenant_id": "synthetic-tenant", "region": {}}]}),
        ):
            with self.subTest(error_type=error_type.__name__):
                activities = ConfigurationActivities(InMemoryConfigurationRepository(tables))
                failures = []

                async def execute_activity_locally(activity, argument, **options):
                    self.assertIs(activity, ConfigurationActivities.load_configuration_activity)
                    try:
                        return await activities.load_configuration_activity(argument)
                    except error_type as error:
                        failure = Failure()
                        DataConverter.default.failure_converter.to_failure(
                            error, DataConverter.default.payload_converter, failure
                        )
                        failures.append(failure)
                        raise

                execute_activity = AsyncMock(side_effect=execute_activity_locally)
                with patch("worksuite_agent.temporal_workflows.workflow.execute_activity", execute_activity):
                    with self.assertRaises(error_type):
                        await GenerateTenantDiagramWorkflow().run("synthetic-tenant")

                self.assertEqual(execute_activity.await_count, 1)
                self.assertEqual(failures[0].application_failure_info.type, error_type.__name__)
                policy = execute_activity.await_args.kwargs.get("retry_policy")
                self.assertIsNotNone(policy)
                self.assertIn(failures[0].application_failure_info.type, policy.non_retryable_error_types)

    async def test_transient_repository_errors_remain_retryable(self):
        for error_type in (OSError, RuntimeError):
            with self.subTest(error_type=error_type.__name__):
                class TransientRepository(ConfigurationRepository):
                    def load_configuration(self, tenant_id):
                        raise error_type("Synthetic temporary repository failure")

                activities = ConfigurationActivities(TransientRepository())
                failures = []

                async def execute_activity_locally(activity, argument, **options):
                    try:
                        return await activities.load_configuration_activity(argument)
                    except error_type as error:
                        failure = Failure()
                        DataConverter.default.failure_converter.to_failure(
                            error, DataConverter.default.payload_converter, failure
                        )
                        failures.append(failure)
                        raise

                execute_activity = AsyncMock(side_effect=execute_activity_locally)
                with patch("worksuite_agent.temporal_workflows.workflow.execute_activity", execute_activity):
                    with self.assertRaises(error_type):
                        await GenerateTenantDiagramWorkflow().run("synthetic-tenant")
                policy = execute_activity.await_args.kwargs.get("retry_policy")
                self.assertIsNotNone(policy)
                self.assertEqual(failures[0].application_failure_info.type, error_type.__name__)
                self.assertNotIn(failures[0].application_failure_info.type, policy.non_retryable_error_types)
                self.assertEqual(policy.maximum_attempts, 0)

    async def test_workflow_runs_both_real_activities_with_thirty_second_timeouts(self):
        repository = InMemoryConfigurationRepository(
            {"tenants": [{"tenant_id": "synthetic-tenant", "name": "Synthetic Tenant"}]}
        )
        activities = ConfigurationActivities(repository)

        async def execute_activity_locally(activity, argument, **options):
            self.assertEqual(options["schedule_to_close_timeout"], timedelta(seconds=30))
            if activity is ConfigurationActivities.load_configuration_activity:
                return await activities.load_configuration_activity(argument)
            return await activity(argument)

        execute_activity = AsyncMock(side_effect=execute_activity_locally)
        with patch("worksuite_agent.temporal_workflows.workflow.execute_activity", execute_activity):
            diagrams = await GenerateTenantDiagramWorkflow().run("synthetic-tenant")

        self.assertEqual(execute_activity.await_count, 2)
        self.assertIs(execute_activity.await_args_list[0].args[0], ConfigurationActivities.load_configuration_activity)
        self.assertIs(execute_activity.await_args_list[1].args[0], build_mermaid_diagrams_activity)
        self.assertNotIn("retry_policy", execute_activity.await_args_list[1].kwargs)
        self.assertRegex(diagrams["module_overview"], r'tenant_\w+\["Synthetic Tenant"\]')
        self.assertIn("flowchart LR", diagrams["workflow_maps"])
        self.assertRegex(diagrams["workflow_maps"], r'\w+\["No workflows configured"\]')
        self.assertIn("graph LR", diagrams["integration_map"])
        self.assertRegex(diagrams["integration_map"], r'\w+\["No integrations configured"\]')


if __name__ == "__main__":
    unittest.main()
