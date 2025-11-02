"""Temporal workflows orchestrating the Worksuite assistant."""
from __future__ import annotations

from typing import Dict

from temporalio import workflow

from .config_models import TenantConfiguration
from .temporal_activities import build_mermaid_diagrams_activity, load_configuration_activity


@workflow.defn
class GenerateTenantDiagramWorkflow:
    """Workflow that loads configuration and produces Mermaid diagrams."""

    @workflow.run
    async def run(self, tenant_id: str) -> Dict[str, str]:
        configuration: TenantConfiguration = await workflow.execute_activity(
            load_configuration_activity,
            tenant_id,
            schedule_to_close_timeout=workflow.timedelta(seconds=30),
        )
        diagrams: Dict[str, str] = await workflow.execute_activity(
            build_mermaid_diagrams_activity,
            configuration,
            schedule_to_close_timeout=workflow.timedelta(seconds=30),
        )
        return diagrams
