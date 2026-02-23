"""
platform_sdk.tier2_reliability.metrics
────────────────────────────────────────
Re-export of tier0_core.metrics for use within tier2 module imports.
Import from here if you are inside tier2_reliability; import from
platform_sdk.tier0_core.metrics (or top-level platform_sdk) from app code.
"""
from platform_sdk.tier0_core.metrics import (  # noqa: F401
    counter,
    gauge,
    histogram,
    start_metrics_server,
)

__all__ = ["counter", "gauge", "histogram", "start_metrics_server"]
