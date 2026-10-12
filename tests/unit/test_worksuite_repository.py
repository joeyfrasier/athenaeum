"""Synthetic regression coverage for tabular tenant configuration loading."""

import unittest

from worksuite_agent.orchestration import generate_diagrams_locally
from worksuite_agent.repository import (
    InMemoryConfigurationRepository,
    build_configuration_from_tables,
)


class TenantTableValidationTests(unittest.TestCase):
    def test_duplicate_resolved_step_ids_are_rejected_before_diagrams(self):
        cases = {
            "explicit_duplicate": [{"step_id": "same"}, {"step_id": "same"}],
            "explicit_then_fallback": [{"step_id": "2"}, {}],
            "fallback_then_explicit": [{}, {"step_id": "1"}],
            "numeric_string_duplicate": [{"step_id": 2}, {"step_id": "2"}],
        }
        for kind, rows in cases.items():
            with self.subTest(kind=kind):
                repository = InMemoryConfigurationRepository(
                    {
                        "tenants": [{"tenant_id": "synthetic-tenant"}],
                        "workflows": [{"workflow_id": "onboarding"}],
                        "workflow_steps": [{"workflow_id": "onboarding", **row} for row in rows],
                    }
                )
                with self.assertRaisesRegex(ValueError, "Duplicate step IDs.*onboarding"):
                    generate_diagrams_locally("synthetic-tenant", repository)

    def test_unique_step_ids_preserve_numeric_defaults(self):
        configuration = build_configuration_from_tables(
            {
                "tenants": [{"tenant_id": "synthetic-tenant"}],
                "workflows": [{"workflow_id": "onboarding"}],
                "workflow_steps": [
                    {"workflow_id": "onboarding", "next_steps": ["2"]},
                    {"workflow_id": "onboarding"},
                    {"workflow_id": "onboarding", "step_id": "named"},
                ],
            }
        )
        self.assertEqual([step.step_id for step in configuration.workflows[0].steps], ["1", "2", "named"])
        self.assertEqual(configuration.workflows[0].steps[0].next_steps, ["2"])

    def test_same_step_id_in_different_workflows_is_allowed(self):
        configuration = build_configuration_from_tables(
            {
                "tenants": [{"tenant_id": "synthetic-tenant"}],
                "workflows": [{"workflow_id": "first"}, {"workflow_id": "second"}],
                "workflow_steps": [
                    {"workflow_id": "first", "step_id": "shared"},
                    {"workflow_id": "second", "step_id": "shared"},
                ],
            }
        )
        self.assertEqual([workflow.steps[0].step_id for workflow in configuration.workflows], ["shared", "shared"])

    def test_missing_tenants_table_raises_validation_error(self):
        with self.assertRaisesRegex(ValueError, "^Missing tenants table$"):
            build_configuration_from_tables({})

    def test_empty_tenant_iterables_raise_validation_error(self):
        exhausted = iter([{"tenant_id": "synthetic-tenant"}])
        next(exhausted)
        empty_tables = {
            "list": [],
            "tuple": (),
            "iterator": iter([]),
            "generator": (row for row in []),
            "exhausted_iterator": exhausted,
        }
        for kind, tenant_rows in empty_tables.items():
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError, "^Missing tenants table$"):
                    build_configuration_from_tables({"tenants": tenant_rows})

    def test_populated_tenant_iterables_keep_the_first_row(self):
        first = {"tenant_id": "synthetic-tenant", "name": "Synthetic Tenant"}
        second = {"tenant_id": "other-tenant", "name": "Other Tenant"}
        tenant_tables = {
            "list": [first, second],
            "tuple": (first, second),
            "iterator": iter([first, second]),
            "generator": (row for row in [first, second]),
        }
        for kind, tenant_rows in tenant_tables.items():
            with self.subTest(kind=kind):
                configuration = build_configuration_from_tables({"tenants": tenant_rows})
                self.assertEqual(configuration.tenant.tenant_id, "synthetic-tenant")
                self.assertEqual(configuration.tenant.name, "Synthetic Tenant")
                if kind in {"iterator", "generator"}:
                    self.assertEqual(next(tenant_rows), second)

    def test_local_diagrams_surface_empty_iterator_validation(self):
        repository = InMemoryConfigurationRepository({"tenants": iter([])})
        with self.assertRaisesRegex(ValueError, "^Missing tenants table$"):
            generate_diagrams_locally("synthetic-tenant", repository)

    def test_local_diagrams_accept_tenant_generator(self):
        repository = InMemoryConfigurationRepository(
            {
                "tenants": (
                    row
                    for row in [{"tenant_id": "synthetic-tenant", "name": "Synthetic Tenant"}]
                ),
                "modules": [{"module_id": "core", "name": "Core"}],
                "workflows": [{"workflow_id": "onboarding", "name": "Onboarding"}],
                "workflow_steps": [
                    {"workflow_id": "onboarding", "step_id": "start", "name": "Start"}
                ],
                "integrations": [{"integration_id": "identity", "name": "Identity"}],
            }
        )
        diagrams = generate_diagrams_locally("synthetic-tenant", repository)
        self.assertEqual(
            set(diagrams), {"module_overview", "workflow_maps", "integration_map"}
        )
        self.assertRegex(diagrams["module_overview"], r'tenant_\w+\["Synthetic Tenant"\]')
        self.assertRegex(diagrams["workflow_maps"], r'step_\w+\["Start')
        self.assertRegex(diagrams["integration_map"], r'integration_\w+\["Identity')


if __name__ == "__main__":
    unittest.main()
