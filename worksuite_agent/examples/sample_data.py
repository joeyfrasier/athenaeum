"""Example tabular payload representing a Worksuite tenant."""

SAMPLE_TABLES = {
    "tenants": [
        {
            "tenant_id": "tenant-123",
            "name": "Acme Corp",
            "region": "us-east-1",
            "status": "active",
        }
    ],
    "modules": [
        {
            "module_id": "core",
            "name": "Core HR",
            "enabled": True,
            "dependencies": [],
            "timezone": "UTC",
        },
        {
            "module_id": "payroll",
            "name": "Payroll",
            "enabled": True,
            "dependencies": ["core"],
            "frequency": "bi-weekly",
        },
        {
            "module_id": "benefits",
            "name": "Benefits",
            "enabled": False,
            "dependencies": ["core"],
        },
    ],
    "workflows": [
        {
            "workflow_id": "onboarding",
            "name": "Employee Onboarding",
            "trigger": "new_hire",
        }
    ],
    "workflow_steps": [
        {
            "workflow_id": "onboarding",
            "step_id": "collect_docs",
            "name": "Collect Documents",
            "action": "HR collects necessary paperwork",
            "next_steps": ["it_setup"],
        },
        {
            "workflow_id": "onboarding",
            "step_id": "it_setup",
            "name": "IT Setup",
            "action": "Provision laptop and accounts",
            "next_steps": ["welcome_email"],
        },
        {
            "workflow_id": "onboarding",
            "step_id": "welcome_email",
            "name": "Welcome Email",
            "action": "Send welcome message",
            "next_steps": [],
        },
    ],
    "integrations": [
        {
            "integration_id": "okta",
            "name": "Okta",
            "type": "SSO",
            "status": "active",
        },
        {
            "integration_id": "netsuite",
            "name": "NetSuite",
            "type": "ERP",
            "status": "active",
        },
    ],
    "automations": [
        {
            "automation_id": "welcome_package",
            "name": "Welcome Package",
            "trigger": "new_hire",
            "actions": ["send_welcome_kit", "notify_manager"],
            "enabled": True,
        }
    ],
}
