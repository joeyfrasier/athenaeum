"""Temporal workflows orchestrating the Worksuite assistant."""
from __future__ import annotations

from datetime import timedelta
from typing import Dict

from temporalio import workflow
from temporalio.common import RetryPolicy

from .config_models import TenantConfiguration
from .temporal_activities import ConfigurationActivities, build_mermaid_diagrams_activity


@workflow.defn
class GenerateTenantDiagramWorkflow:
    """Workflow that loads configuration and produces Mermaid diagrams."""

    @workflow.run
    async def run(self, tenant_id: str) -> Dict[str, str]:
        configuration: TenantConfiguration = await workflow.execute_activity(
            ConfigurationActivities.load_configuration_activity,
            tenant_id,
            schedule_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(non_retryable_error_types=["ValueError", "KeyError", "ValidationError"]),
        )
        diagrams: Dict[str, str] = await workflow.execute_activity(
            build_mermaid_diagrams_activity,
            configuration,
            schedule_to_close_timeout=timedelta(seconds=30),
        )
        return diagrams
