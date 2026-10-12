"""Regression coverage for valid diagrams with realistic tenant identifiers."""

import re
import unittest

from worksuite_agent.repository import build_configuration_from_tables
from worksuite_agent.visualization import MermaidDiagramBuilder


def builder_for(**tables):
    return MermaidDiagramBuilder(
        build_configuration_from_tables(
            {"tenants": [{"tenant_id": "synthetic-tenant", "name": "Synthetic Tenant"}], **tables}
        )
    )


def defined_nodes(diagram):
    nodes = "\n".join(line for line in diagram.splitlines() if not line.lstrip().startswith("subgraph "))
    return re.findall(r'\b([A-Za-z0-9_]+)(?=\[|\(\()', nodes)


class MermaidDiagramTests(unittest.TestCase):
    def test_tenant_only_export_has_graphs_for_empty_configuration_sections(self):
        diagrams = builder_for().build_all()
        for kind, message in (
            ("workflow_maps", "No workflows configured"),
            ("integration_map", "No integrations configured"),
        ):
            with self.subTest(kind=kind):
                diagram = diagrams[kind]
                self.assertIn(message, diagram)
                headers = [line for line in diagram.splitlines() if re.match(r"^(graph|flowchart) ", line)]
                self.assertEqual(len(headers), 1)
                self.assertEqual(len(defined_nodes(diagram)), 1)
                self.assertRegex(diagram, rf'\w+\["{message}"\]')

    def test_multiple_workflows_have_one_header_and_separate_step_nodes(self):
        builder = builder_for(
            workflows=[
                {"workflow_id": "hire-hr", "name": "Hiring HR"},
                {"workflow_id": "hire_hr", "name": "Hiring IT"},
            ],
            workflow_steps=[
                {"workflow_id": workflow_id, "step_id": step_id,
                 "name": f"{workflow_id} {step_id}", "next_steps": next_steps}
                for workflow_id in ("hire-hr", "hire_hr")
                for step_id, next_steps in (("start", ["finish"]), ("finish", []))
            ],
        )
        diagram = builder.build_workflow_maps()
        self.assertEqual(diagram.splitlines().count("flowchart LR"), 1)
        nodes = defined_nodes(diagram)
        self.assertEqual(len(nodes), 4)
        self.assertEqual(len(set(nodes)), 4)
        groups = re.findall(r"(?m)^[ \t]*subgraph [^\n]*\n(.*?)^[ \t]*end$", diagram, re.DOTALL)
        self.assertEqual(len(groups), 2)
        for group in groups:
            group_nodes = set(defined_nodes(group))
            self.assertEqual(len(group_nodes), 2)
            edges = re.findall(r"(\w+) --> (\w+)", group)
            self.assertEqual(len(edges), 1)
            self.assertEqual(set(edges[0]), group_nodes)

    def test_labels_encode_quotes_and_do_not_inject_graph_syntax(self):
        unsafe = 'Quoted "name" & <tag> #34; `unbalanced\nflowchart LR'
        builder = builder_for(
            tenants=[{"tenant_id": "synthetic-tenant", "name": unsafe}],
            modules=[{"module_id": "core", "name": unsafe}],
            workflows=[{"workflow_id": "hire", "name": unsafe}],
            workflow_steps=[
                {"workflow_id": "hire", "step_id": "start", "name": unsafe, "action": unsafe}
            ],
            integrations=[{"integration_id": "identity", "name": unsafe, "type": unsafe}],
        )
        for kind, diagram in builder.build_all().items():
            with self.subTest(kind=kind):
                self.assertNotIn('Quoted "name"', diagram)
                self.assertIn("#34;name#34;", diagram)
                self.assertIn("#35;34;", diagram)
                self.assertIn("#60;tag#62;", diagram)
                self.assertNotIn("`", diagram)
                self.assertIn("#96;unbalanced", diagram)
                for line in diagram.splitlines():
                    if '"' in line:
                        self.assertEqual(line.count('"'), 2)
                headers = [line for line in diagram.splitlines() if re.match(r"^(graph|flowchart) ", line)]
                self.assertEqual(len(headers), 1)

    def test_colliding_module_and_integration_ids_stay_distinct(self):
        builder = builder_for(
            modules=[
                {"module_id": "core-hr", "name": "Hyphen", "dependencies": ["core_hr"]},
                {"module_id": "core_hr", "name": "Underscore"},
            ],
            integrations=[
                {"integration_id": "identity-login", "name": "Hyphen"},
                {"integration_id": "identity_login", "name": "Underscore"},
            ],
        )
        modules = builder.build_module_overview()
        module_nodes = re.findall(r'(\w+)\[/"(Hyphen|Underscore)', modules)
        self.assertEqual(len(module_nodes), 2)
        by_label = {label: node for node, label in module_nodes}
        self.assertNotEqual(by_label["Hyphen"], by_label["Underscore"])
        self.assertIn(f'{by_label["Underscore"]} --> {by_label["Hyphen"]}', modules)
        integrations = builder.build_integration_map()
        integration_nodes = re.findall(r'(\w+)\["(Hyphen|Underscore)', integrations)
        self.assertEqual(len(set(node for node, _ in integration_nodes)), 2)
        self.assertEqual(builder.build_all(), builder.build_all())

    def test_empty_workflows_have_distinct_placeholder_nodes(self):
        diagram = builder_for(
            workflows=[{"workflow_id": "first", "name": "First"}, {"workflow_id": "second", "name": "Second"}]
        ).build_workflow_maps()
        nodes = defined_nodes(diagram)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(set(nodes)), 2)


if __name__ == "__main__":
    unittest.main()
