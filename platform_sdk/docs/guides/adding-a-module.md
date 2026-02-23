# Adding a Module

Adding a new capability to platform_sdk takes ≤5 steps.
`mcp_server.py` and `__init__.py` are **never touched**.

---

## The ≤5-Step Checklist

### Step 1 — Write the module

Place it in the right tier directory using the 5-phase pattern:

```python
# platform_sdk/tier0_core/mymodule.py
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class MyProvider(Protocol):
    """Provider interface — swap backends without changing call sites."""
    def do_thing(self, x: str) -> str: ...

class MockMyProvider:
    """Deterministic mock — no external deps. Used in tests."""
    def do_thing(self, x: str) -> str:
        return f"mock:{x}"

_provider = None

def get_provider():
    global _provider
    if _provider is None:
        import os
        backend = os.getenv("PLATFORM_MYMODULE_BACKEND", "mock")
        if backend == "mock":
            _provider = MockMyProvider()
        # add real providers here
    return _provider

def do_thing(x: str) -> str:
    """Public API — call this, not get_provider() directly."""
    return get_provider().do_thing(x)
```

**Tier placement rules:**

| Tier | Import rule | Examples |
|------|-------------|---------|
| tier0_core | Cannot import from any other tier | logging, errors, config |
| tier1_runtime | May import tier0 only | context, validate, retry |
| tier2_reliability | May import tier0–tier1 | health, audit, cache |
| tier3_platform | May import tier0–tier2 | vector, authorization |
| tier4_advanced | May import tier0–tier3 | inference, llm_obs |

---

### Step 2 — Add `__sdk_export__`

At the bottom of your module, declare its metadata:

```python
# Optional: MCP handlers (only for agent-facing modules)
async def _mcp_do_thing(args: dict) -> dict:
    result = do_thing(args["x"])
    return {"result": result}


__sdk_export__ = {
    "surface": "agent",          # "agent" | "service" | "both"
    "exports": ["do_thing"],
    "mcp_tools": [               # omit if not agent-facing via MCP
        {
            "name": "do_thing",
            "description": "Do the thing via platform_sdk.",
            "schema": {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
            "handler": "_mcp_do_thing",
        },
    ],
    "description": "One-line description of what this module does",
    "tier": "tier0_core",
    "module": "mymodule",
}
```

`"surface"` values:
- `"agent"` — visible in `platform_sdk.agent` and via MCP
- `"service"` — visible in `platform_sdk.service` (and `platform_sdk` itself) only
- `"both"` — visible in both (e.g., `errors`)

---

### Step 3 — Add one tuple to `_registry.py`

```python
# platform_sdk/_registry.py
TIER_MODULES: list[tuple[str, str]] = [
    ...
    ("tier0_core", "mymodule"),   # ← add this line
    ...
]
```

After this step, `collect_mcp_tools()` automatically discovers your MCP tool.
`mcp_server.py` does not need to be edited.

---

### Step 4 — Add one import line to `agent.py` and/or `service.py`

If `surface = "agent"` or `"both"`:

```python
# platform_sdk/agent.py
from platform_sdk.tier0_core.mymodule import do_thing   # ← add this line
# also add "do_thing" to __all__
```

If `surface = "service"` or `"both"`:

```python
# platform_sdk/service.py
from platform_sdk.tier0_core.mymodule import do_thing   # ← add this line
# also add "do_thing" to __all__
```

`__init__.py` does not need to be edited — it re-exports everything from `service.py`.

---

### Step 5 (optional) — Add docs

Create a one-line stub and mkdocstrings renders the API reference from docstrings:

```markdown
<!-- docs/api/tier0/mymodule.md -->
# mymodule

::: platform_sdk.tier0_core.mymodule
```

Add one nav entry in `mkdocs.yml`:

```yaml
- Tier 0 Core:
  - mymodule: api/tier0/mymodule.md   # ← add this line
```

---

## Checklist summary

| Step | File(s) changed | Required? |
|------|----------------|-----------|
| 1. Write the module | `tier*/mymodule.py` | Yes |
| 2. Add `__sdk_export__` | same file | Yes |
| 3. Add to `_registry.py` | `_registry.py` | Yes |
| 4. Add import | `agent.py` and/or `service.py` | Yes |
| 5. Add docs stub + nav | `docs/api/.../mymodule.md`, `mkdocs.yml` | Optional |

`mcp_server.py` — **never touched**.
`__init__.py` — **never touched**.
