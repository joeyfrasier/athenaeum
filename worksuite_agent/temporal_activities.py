"""Temporal activities for the Worksuite configuration assistant."""
from __future__ import annotations

from typing import Dict, Optional

from temporalio import activity

from .config_models import TenantConfiguration
from .repository import ConfigurationRepository
from .visualization import MermaidDiagramBuilder

_REPOSITORY: Optional[ConfigurationRepository] = None


def configure_repository(repository: Optional[ConfigurationRepository]) -> None:
    """Configure the repository used by activities when running under Temporal."""

    global _REPOSITORY
    _REPOSITORY = repository


@activity.defn
async def load_configuration_activity(tenant_id: str) -> TenantConfiguration:
    """Load tenant configuration data from the configured repository."""

    if _REPOSITORY is None:  # pragma: no cover - guard for misconfiguration
        raise RuntimeError("Repository not configured for activities")
    configuration = _REPOSITORY.load_configuration(tenant_id)
    return configuration


@activity.defn
async def build_mermaid_diagrams_activity(configuration: TenantConfiguration) -> Dict[str, str]:
    """Transform configuration data into Mermaid diagrams."""

    builder = MermaidDiagramBuilder(configuration)
    return builder.build_all()
