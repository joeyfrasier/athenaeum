"""Repositories for loading Worksuite tenant configuration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, Mapping

from .config_models import TenantConfiguration


class ConfigurationRepository(ABC):
    """Contract for retrieving tenant configuration across tables."""

    @abstractmethod
    def load_configuration(self, tenant_id: str) -> TenantConfiguration:
        """Return the entire configuration for the requested tenant."""


class TabularConfigurationRepository(ConfigurationRepository):
    """Repository that reads raw table data before constructing a configuration object."""

    @abstractmethod
    def load_tables(self, tenant_id: str) -> Mapping[str, Iterable[Mapping[str, object]]]:
        """Return a mapping of table name -> iterable of rows."""

    def load_configuration(self, tenant_id: str) -> TenantConfiguration:
        return build_configuration_from_tables(self.load_tables(tenant_id))


def build_configuration_from_tables(
    tables: Mapping[str, Iterable[Mapping[str, object]]]
) -> TenantConfiguration:
    """Create :class:`TenantConfiguration` from generic table payloads."""

    tenant_table = tables.get("tenants")
    if not tenant_table:
        raise ValueError("Missing tenants table")

    tenant_row = next(iter(tenant_table))

    modules_data = tables.get("modules", [])
    workflows_data = tables.get("workflows", [])
    workflow_steps_data = tables.get("workflow_steps", [])
    integrations_data = tables.get("integrations", [])
    automations_data = tables.get("automations", [])

    # Index workflow steps by workflow id for convenience
    steps_by_workflow: Dict[str, list[dict]] = {}
    for row in workflow_steps_data:
        steps_by_workflow.setdefault(str(row.get("workflow_id")), []).append(row)

    from .config_models import (
        AutomationConfig,
        IntegrationConfig,
        ModuleConfig,
        TenantConfiguration,
        TenantInfo,
        WorkflowConfig,
        WorkflowStep,
    )

    tenant = TenantInfo(
        tenant_id=str(tenant_row["tenant_id"]),
        name=str(tenant_row.get("name", tenant_row["tenant_id"])),
        region=tenant_row.get("region"),
        status=tenant_row.get("status", "active"),
    )

    modules = [
        ModuleConfig(
            module_id=str(row["module_id"]),
            name=str(row.get("name", row["module_id"])),
            enabled=bool(row.get("enabled", True)),
            settings={k: str(v) for k, v in row.items() if k not in {"module_id", "name", "enabled", "dependencies"}},
            dependencies=[str(dep) for dep in row.get("dependencies", [])],
        )
        for row in modules_data
    ]

    workflows = []
    for row in workflows_data:
        workflow_id = str(row["workflow_id"])
        steps = [
            WorkflowStep(
                step_id=str(step_row.get("step_id", idx + 1)),
                name=str(step_row.get("name", f"Step {idx+1}")),
                action=str(step_row.get("action", "")),
                next_steps=[str(s) for s in step_row.get("next_steps", [])],
            )
            for idx, step_row in enumerate(steps_by_workflow.get(workflow_id, []))
        ]
        workflows.append(
            WorkflowConfig(
                workflow_id=workflow_id,
                name=str(row.get("name", workflow_id)),
                description=row.get("description"),
                trigger=str(row.get("trigger", "manual")),
                steps=steps,
            )
        )

    integrations = [
        IntegrationConfig(
            integration_id=str(row["integration_id"]),
            name=str(row.get("name", row["integration_id"])),
            type=str(row.get("type", "custom")),
            status=str(row.get("status", "active")),
            metadata={k: str(v) for k, v in row.items() if k not in {"integration_id", "name", "type", "status"}},
        )
        for row in integrations_data
    ]

    automations = [
        AutomationConfig(
            automation_id=str(row["automation_id"]),
            name=str(row.get("name", row["automation_id"])),
            trigger=str(row.get("trigger", "manual")),
            actions=[str(a) for a in row.get("actions", [])],
            enabled=bool(row.get("enabled", True)),
        )
        for row in automations_data
    ]

    return TenantConfiguration(
        tenant=tenant,
        modules=modules,
        workflows=workflows,
        integrations=integrations,
        automations=automations,
    )


class InMemoryConfigurationRepository(TabularConfigurationRepository):
    """Repository backed by an in-memory dictionary of table data."""

    def __init__(self, table_data: Mapping[str, Iterable[Mapping[str, object]]]):
        self._table_data = table_data

    def load_tables(self, tenant_id: str):  # type: ignore[override]
        # For this simple example we ignore tenant_id and assume data is scoped.
        return self._table_data
