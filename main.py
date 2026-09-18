import os
import sys

# In a PyInstaller --windowed build, sys.stdout/stderr are None (no console),
# which crashes any library that prints on import (e.g. pygame's greeting)
# before our own error handling ever runs. Neutralize both cases up front.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import threading
import time

from jarvis import config
from jarvis.audio import stt, tts, wakeword
from jarvis.brain import llm
from jarvis.control import cancel_event, shutdown_event
from jarvis.ui.overlay import FloatingOverlay
from jarvis.ui.setup_wizard import run_setup_wizard
from jarvis.ui.tray import TrayIcon


def build_app():
    def shutdown():
        shutdown_event.set()
        cancel_event.set()
        tray.stop()
        overlay.close()

    overlay = FloatingOverlay(on_stop=cancel_event.set, on_quit=shutdown)
    tray = TrayIcon(on_show_log=overlay.show, on_quit=shutdown)

    return overlay, tray


def think(command: str):
    """Runs the LLM in a daemon worker thread so a cancel gesture can abandon
    it immediately, without waiting for the in-flight network call."""
    result = {}

    def worker():
        result["reply"] = llm.process(command)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    while t.is_alive():
        if cancel_event.is_set():
            return None
        time.sleep(0.05)
    return result.get("reply")


def assistant_loop(overlay, tray):
    overlay.log("Initialising Jarvis...")
    tts.speak("Initialising Jarvis")

    while not shutdown_event.is_set():
        overlay.set_status("idle")
        tray.set_status("idle")

        detected = wakeword.wait_for_wakeword(shutdown_event)
        if not detected or shutdown_event.is_set():
            break

        overlay.log("Wake word detected.")
        overlay.set_status("listening")
        tray.set_status("listening")

        command = stt.listen_for_command()
        if not command:
            continue

        overlay.log(f"You: {command}")

        reply = think(command)
        if shutdown_event.is_set():
            break
        if cancel_event.is_set():
            cancel_event.clear()
            continue

        overlay.log(f"Jarvis: {reply}")
        overlay.set_status("speaking")
        tray.set_status("speaking")
        tts.speak(reply, cancel_event=cancel_event)
        cancel_event.clear()

    overlay.close()


def main():
    if not config.is_configured():
        run_setup_wizard()
    if not config.is_configured():
        return  # user closed the setup wizard without saving a key

    overlay, tray = build_app()
    tray.run_detached()

    audio_thread = threading.Thread(
        target=assistant_loop, args=(overlay, tray), daemon=True
    )
    audio_thread.start()

    overlay.run()  # blocks main thread until the overlay is destroyed


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        try:
            import tkinter as tk
            from tkinter import messagebox

            err_root = tk.Tk()
            err_root.withdraw()
            messagebox.showerror("Jarvis crashed", traceback.format_exc())
        except Exception:
            pass
        raise
