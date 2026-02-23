"""
platform_sdk
────────────
Stable top-level exports. Import from here, not from sub-modules directly.
Every name exported here is part of the public API and subject to semver.

Internally delegates to ``platform_sdk.service``, which is the full service
surface. Agents that want a narrower import contract should use
``platform_sdk.agent`` instead.
"""
from platform_sdk.service import *  # noqa: F401, F403
from platform_sdk.service import __all__  # noqa: F401 — re-export for linters/mypy

__version__ = "0.1.0"
