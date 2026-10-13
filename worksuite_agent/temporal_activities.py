"""Temporal activities for the Worksuite configuration assistant."""
from __future__ import annotations

from typing import Dict

from temporalio import activity

from .config_models import TenantConfiguration
from .repository import ConfigurationRepository
from .visualization import MermaidDiagramBuilder

class ConfigurationActivities:
    """Configuration activities bound to one invocation's repository."""

    def __init__(self, repository: ConfigurationRepository):
        self._repository = repository

    @activity.defn
    async def load_configuration_activity(self, tenant_id: str) -> TenantConfiguration:
        """Load tenant configuration from this worker's repository."""

        return self._repository.load_configuration(tenant_id)


@activity.defn
async def build_mermaid_diagrams_activity(configuration: TenantConfiguration) -> Dict[str, str]:
    """Transform configuration data into Mermaid diagrams."""

    builder = MermaidDiagramBuilder(configuration)
    return builder.build_all()
