"""Utilities to run the Temporal workflow locally or via a Temporal server."""
from __future__ import annotations

from typing import Dict
from uuid import uuid4

from temporalio.client import Client
from temporalio.worker import Worker

from .config_models import TenantConfiguration
from .repository import ConfigurationRepository
from .temporal_activities import (
    ConfigurationActivities,
    build_mermaid_diagrams_activity,
)
from .temporal_workflows import GenerateTenantDiagramWorkflow
from .visualization import MermaidDiagramBuilder


async def run_workflow(
    temporal_address: str,
    tenant_id: str,
    repository: ConfigurationRepository,
) -> Dict[str, str]:
    """Execute a workflow with a dedicated worker and repository on Temporal."""

    client = await Client.connect(temporal_address)
    invocation_id = uuid4().hex
    task_queue = f"worksuite-assistant-{invocation_id}"
    activities = ConfigurationActivities(repository)
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[GenerateTenantDiagramWorkflow],
        activities=[activities.load_configuration_activity, build_mermaid_diagrams_activity],
    ):
        return await client.execute_workflow(
            GenerateTenantDiagramWorkflow.run,
            tenant_id,
            id=f"tenant-diagram-{tenant_id}-{invocation_id}",
            task_queue=task_queue,
        )


def generate_diagrams_locally(
    tenant_id: str,
    repository: ConfigurationRepository,
) -> Dict[str, str]:
    """Fallback helper that bypasses Temporal and executes synchronously.

    Useful for unit tests and for the Streamlit UI running without a Temporal
    server. The logic mirrors the activities that would normally execute inside
    Temporal.
    """

    configuration: TenantConfiguration = repository.load_configuration(tenant_id)
    builder = MermaidDiagramBuilder(configuration)
    return builder.build_all()
