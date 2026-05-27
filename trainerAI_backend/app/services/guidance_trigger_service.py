"""
Per-session trigger state for perception-driven guidance.

Drop-on-busy semantics: if a pipeline run is already in flight for a session,
additional trigger attempts are silently dropped rather than queued.
"""
import asyncio

# Both dicts grow with each unique session_id and are never evicted. This is intentional
# for the single-developer workstation deployment (one session per run); do not use in
# a multi-tenant / long-running server without adding an LRU eviction strategy.
_last_triggered_tool: dict[str, str] = {}
_inflight: dict[str, asyncio.Lock] = {}


def _get_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _inflight:
        _inflight[session_id] = asyncio.Lock()
    return _inflight[session_id]


def should_trigger(session_id: str, active_tool: str) -> bool:
    """True iff active_tool differs from the last tool triggered for this session."""
    return _last_triggered_tool.get(session_id) != active_tool


def mark_triggered(session_id: str, active_tool: str) -> None:
    """Record the tool we are about to dispatch guidance for."""
    _last_triggered_tool[session_id] = active_tool


async def try_acquire(session_id: str) -> bool:
    """Non-blocking lock acquire. Returns False if a pipeline run is already in flight."""
    lock = _get_lock(session_id)
    if lock.locked():
        return False
    await lock.acquire()
    return True


def release(session_id: str) -> None:
    """Release the per-session lock. Idempotent."""
    lock = _get_lock(session_id)
    if lock.locked():
        lock.release()
