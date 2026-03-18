"""Process-local registry of active test contexts for interrupt cleanup.

Tracks DriftTestContext objects so atexit can tear them down if the process
is interrupted before normal finally-block cleanup runs.
"""

from __future__ import annotations

import atexit
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drift_adoption_helpers import DriftTestContext

_active: dict[str, DriftTestContext] = {}
_atexit_registered = False


def register(ctx: DriftTestContext) -> None:
    """Track a context for cleanup on unexpected exit."""
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_atexit_cleanup)
        _atexit_registered = True
    _active[ctx.stack_name] = ctx


def unregister(ctx: DriftTestContext) -> None:
    """Remove a context after normal teardown completes."""
    _active.pop(ctx.stack_name, None)


def cleanup_all() -> int:
    """Tear down all registered contexts. Returns count cleaned."""
    from drift_adoption_helpers import teardown_drift_test

    cleaned = 0
    for name, ctx in list(_active.items()):
        try:
            print(f"[cleanup] Destroying orphaned stack: {name}")
            teardown_drift_test(ctx)
            cleaned += 1
        except Exception as e:
            warnings.warn(f"[cleanup] Failed to teardown {name}: {e}")
        finally:
            _active.pop(name, None)
    return cleaned


def _atexit_cleanup() -> None:
    if _active:
        print(f"\n[cleanup] atexit: {len(_active)} stack(s) still active, cleaning up...")
        cleanup_all()
