# platform_sdk Tooling Guide

Tooling recommendations for documentation, API exploration, and agent-friendly consumption.

---

## Documentation

### MkDocs Material + mkdocstrings (Recommended)

Auto-generates API reference from module docstrings. Used by this project.

```bash
pip install mkdocs-material mkdocstrings[python]
mkdocs serve   # live preview at http://localhost:8000
mkdocs build   # static output in ./site
```

Configure via `docs/mkdocs.yml`.

**Best for:** internal teams, GitHub Pages, Backstage TechDocs pipeline.

---

### Scalar

Beautiful, interactive OpenAPI documentation for your HTTP API layer.

```python
# FastAPI integration
from scalar_fastapi import get_scalar_api_reference

@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(openapi_url="/openapi.json", title="Platform API")
```

**Best for:** external developer portals, partner API docs.

---

### Docusaurus / Starlight

Full documentation site with versioning, search, and blog.

- **Docusaurus** — Meta's framework (React-based)
- **Starlight** — Astro-based, faster builds

**Best for:** large SDKs with guides, tutorials, and changelogs.

---

### Fern (Upgrade Path)

Generate SDKs, Postman collections, and API docs from an OpenAPI spec.
Automates client library generation for TypeScript, Python, Go, Java.

**Best for:** multi-language SDK distribution once the API surface stabilizes.

---

## API Exploration

| Tool | Use Case |
|------|----------|
| **Scalar** | Interactive HTTP API docs |
| **Swagger UI** | OpenAPI browser (FastAPI built-in) |
| **Postman** | Manual API testing |
| **HTTPie** | CLI API testing |
| **pytest** | Automated contract testing |

---

## Agent Integration

### MCP Server

Expose platform_sdk as MCP tools for Claude/Cursor agents:

```bash
python -m platform_sdk.mcp_server
```

Tools available: `call_inference`, `query_vector`, `upsert_vector`, `log_event`,
`emit_metric`, `check_health`, `audit_event`, `check_rate_limit`, `get_secret`, `embed_text`.

### Import Contract

Agents that write Python code should import only from `platform_sdk`:

```python
# Correct — single import path
from platform_sdk import get_logger, complete, vector_search

# Incorrect — bypasses platform_sdk
import structlog
from openai import OpenAI
```

---

## Observability Stack

| Concern | OSS Tool | Enterprise |
|---------|----------|------------|
| Metrics | Prometheus + Grafana | Datadog |
| Logs | Loki + Grafana | Splunk / Datadog |
| Traces | Jaeger / Tempo | Datadog APM |
| LLM Obs | Langfuse | Langfuse Cloud |
| Uptime | Prometheus Alertmanager | PagerDuty |
