"""Data models describing Worksuite tenant configuration."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TenantInfo(BaseModel):
    """Metadata about the tenant itself."""

    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Human readable tenant name")
    region: Optional[str] = Field(None, description="Region or data center")
    status: str = Field("active", description="Lifecycle status")


class ModuleConfig(BaseModel):
    """Configuration of a core Worksuite module."""

    module_id: str
    name: str
    enabled: bool = True
    settings: Dict[str, str] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list, description="Other module IDs")


class WorkflowStep(BaseModel):
    step_id: str
    name: str
    action: str
    next_steps: List[str] = Field(default_factory=list)


class WorkflowConfig(BaseModel):
    workflow_id: str
    name: str
    description: Optional[str] = None
    trigger: str = "manual"
    steps: List[WorkflowStep] = Field(default_factory=list)


class IntegrationConfig(BaseModel):
    integration_id: str
    name: str
    type: str
    status: str = "active"
    metadata: Dict[str, str] = Field(default_factory=dict)


class AutomationConfig(BaseModel):
    automation_id: str
    name: str
    trigger: str
    actions: List[str] = Field(default_factory=list)
    enabled: bool = True


class TenantConfiguration(BaseModel):
    """Aggregated configuration for a tenant."""

    tenant: TenantInfo
    modules: List[ModuleConfig] = Field(default_factory=list)
    workflows: List[WorkflowConfig] = Field(default_factory=list)
    integrations: List[IntegrationConfig] = Field(default_factory=list)
    automations: List[AutomationConfig] = Field(default_factory=list)

    def modules_by_id(self) -> Dict[str, ModuleConfig]:
        return {module.module_id: module for module in self.modules}
