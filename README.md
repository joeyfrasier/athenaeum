# 🤖 Worksuite SE Assistant

This repository contains a Streamlit prototype for the Worksuite Solution Engineering (SE) Assistant. The
application demonstrates how Temporal workflows can orchestrate activities that read Worksuite tenant
configuration data and generate Mermaid diagrams to visualize the tenant.

## Features

- **Temporal-first architecture** – Workflows and activities are defined with [`temporalio`](https://python.temporal.io/)
  so the same logic can run locally or against a Temporal cluster.
- **Configuration ingestion** – Load tabular tenant data from JSON (mirroring database tables) or use the bundled
  sample dataset.
- **Diagram generation** – Build module, workflow, and integration diagrams in Mermaid format, ready to embed in SE
  deliverables.
- **Streamlit UI** – Upload configuration exports, inspect a configuration summary, and copy Mermaid diagrams.

## Running the app locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

When uploading custom data, provide a JSON object that maps each Worksuite table name to an array of rows. See
[`worksuite_agent/examples/sample_data.py`](worksuite_agent/examples/sample_data.py) for an example export.

## Temporal integration

The Streamlit experience executes the workflow logic locally to simplify the demo. To connect to a running Temporal
cluster you can call `worksuite_agent.orchestration.run_workflow` with the Temporal address and repository that knows
how to read Worksuite tables.

```python
import asyncio
from worksuite_agent.orchestration import run_workflow
from worksuite_agent.repository import MyDjangoRepository

async def main():
    diagrams = await run_workflow(
        temporal_address="localhost:7233",
        tenant_id="tenant-123",
        repository=MyDjangoRepository(),
    )
    print(diagrams)

asyncio.run(main())
```

Replace `MyDjangoRepository` with a repository that reads the required tables from the Worksuite database.
