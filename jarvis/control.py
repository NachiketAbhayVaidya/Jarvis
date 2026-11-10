import threading

shutdown_event = threading.Event()
cancel_event = threading.Event()

_shutdown_handler = None


def register_shutdown_handler(fn):
    """Registers the full app-shutdown routine (tray/overlay/server teardown)
    so callers like the remote API can trigger it without importing main.py."""
    global _shutdown_handler
    _shutdown_handler = fn


def request_shutdown():
    if _shutdown_handler is not None:
        _shutdown_handler()
    else:
        shutdown_event.set()
        cancel_event.set()
