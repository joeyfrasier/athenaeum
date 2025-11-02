"""Helpers for transforming tenant configuration into diagrams."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List

from .config_models import ModuleConfig, TenantConfiguration, WorkflowConfig


def _mermaid_id(raw: str, prefix: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", raw)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned:
        return f"{prefix}_{cleaned}" if prefix else cleaned
    return prefix or "node"


class MermaidDiagramBuilder:
    """Builds Mermaid diagrams from Worksuite tenant configuration."""

    def __init__(self, configuration: TenantConfiguration):
        self.configuration = configuration

    def build_all(self) -> Dict[str, str]:
        return {
            "module_overview": self.build_module_overview(),
            "workflow_maps": self.build_workflow_maps(),
            "integration_map": self.build_integration_map(),
        }

    def build_module_overview(self) -> str:
        tenant_name = self.configuration.tenant.name
        tenant_node = _mermaid_id(self.configuration.tenant.tenant_id, "tenant")
        lines = ["%% Worksuite module overview", "graph TD", f"    {tenant_node}[\"{tenant_name}\"]"]
        for module in self.configuration.modules:
            module_node = _mermaid_id(module.module_id, "module")
            label = f"{module.name}\\n({'Enabled' if module.enabled else 'Disabled'})"
            lines.append(f"    {tenant_node} --> {module_node}[/\"{label}\"/]")
            for dependency in module.dependencies:
                dependency_node = _mermaid_id(dependency, "module")
                lines.append(f"    {dependency_node} --> {module_node}")
        return "\n".join(lines)

    def build_workflow_maps(self) -> str:
        diagrams: List[str] = []
        for workflow in self.configuration.workflows:
            diagrams.append(self._build_workflow_diagram(workflow))
        return "\n\n".join(diagrams) if diagrams else "%% No workflows configured"

    def _build_workflow_diagram(self, workflow: WorkflowConfig) -> str:
        lines = [
            f"%% Workflow: {workflow.name}",
            "flowchart LR",
        ]
        if not workflow.steps:
            lines.append("    Empty[(No steps configured)]")
            return "\n".join(lines)

        for step in workflow.steps:
            step_node = _mermaid_id(step.step_id, "step")
            lines.append(
                f"    {step_node}[\"{step.name}\\n{step.action}\"]"
            )
        for step in workflow.steps:
            source_node = _mermaid_id(step.step_id, "step")
            for target in step.next_steps or []:
                target_node = _mermaid_id(target, "step")
                lines.append(f"    {source_node} --> {target_node}")
        return "\n".join(lines)

    def build_integration_map(self) -> str:
        if not self.configuration.integrations:
            return "%% No integrations configured"

        tenant_node = _mermaid_id(self.configuration.tenant.tenant_id, "tenant")
        lines = [
            "graph LR",
            f"    {tenant_node}((\"{self.configuration.tenant.name}\"))",
        ]
        for integration in self.configuration.integrations:
            integration_node = _mermaid_id(integration.integration_id, "integration")
            label = f"{integration.name}\\n{integration.type}"
            lines.append(f"    {tenant_node} --- {integration_node}[\"{label}\"]")
        return "\n".join(lines)


def summarize_configuration(configuration: TenantConfiguration) -> List[str]:
    """Return human readable bullet points summarizing the tenant."""

    modules_summary = _summarize_modules(configuration.modules)
    workflow_count = len(configuration.workflows)
    integration_count = len(configuration.integrations)
    automation_count = len(configuration.automations)

    summary = [
        f"Tenant **{configuration.tenant.name}** ({configuration.tenant.tenant_id})",
        f"Modules enabled: {modules_summary}",
        f"Workflows configured: {workflow_count}",
        f"Integrations configured: {integration_count}",
        f"Automations configured: {automation_count}",
    ]
    return summary


def _summarize_modules(modules: Iterable[ModuleConfig]) -> str:
    enabled = [module.name for module in modules if module.enabled]
    disabled = [module.name for module in modules if not module.enabled]

    pieces: List[str] = []
    if enabled:
        pieces.append(f"enabled ({', '.join(enabled)})")
    if disabled:
        pieces.append(f"disabled ({', '.join(disabled)})")
    return "; ".join(pieces) if pieces else "none"
