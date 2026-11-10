"""Thread-safe event hub bridging the (sync) voice-loop/UI threads and the
async WebSocket server. Stdlib-only so lightweight modules like
jarvis/ui/overlay.py can import it without pulling in fastapi/uvicorn.
"""

import asyncio
import time
from collections import deque
from threading import Lock

_MAX_EVENTS = 200

_events = deque(maxlen=_MAX_EVENTS)
_events_lock = Lock()

_subscribers = set()
_subscribers_lock = Lock()

_loop = None
last_status = "idle"


def set_loop(loop):
    """Called once from the FastAPI app's startup hook."""
    global _loop
    _loop = loop


def publish(event: dict):
    """Records an event and pushes it to any connected WebSocket clients.
    Safe to call from any thread (voice loop, HTTP threadpool, etc.)."""
    global last_status
    event = {**event, "ts": time.time()}
    if event.get("type") == "status":
        last_status = event.get("status", last_status)

    with _events_lock:
        _events.append(event)

    with _subscribers_lock:
        subscribers = list(_subscribers)

    if _loop is None:
        return
    for queue in subscribers:
        _loop.call_soon_threadsafe(queue.put_nowait, event)


def recent(limit: int = 100):
    with _events_lock:
        events = list(_events)
    return events[-limit:]


def subscribe():
    """Registers a new per-connection queue; call unsubscribe(queue) when done."""
    queue = asyncio.Queue()
    with _subscribers_lock:
        _subscribers.add(queue)
    return queue


def unsubscribe(queue):
    with _subscribers_lock:
        _subscribers.discard(queue)
