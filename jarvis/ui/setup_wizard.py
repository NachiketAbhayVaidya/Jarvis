import tkinter as tk
import webbrowser
from tkinter import messagebox

from .. import config

_GROQ_KEYS_URL = "https://console.groq.com/keys"


def run_setup_wizard():
    """Blocking first-run dialog. Returns once the user has saved a working
    key (or force-quit the app)."""
    root = tk.Tk()
    root.title("Jarvis Setup")
    root.geometry("420x260")
    root.resizable(False, False)

    tk.Label(
        root,
        text="Welcome to Jarvis",
        font=("Segoe UI", 14, "bold"),
    ).pack(pady=(20, 4))

    tk.Label(
        root,
        text="Jarvis needs a free Groq API key to think.\nPaste yours below to get started.",
        font=("Segoe UI", 10),
        justify="center",
    ).pack(pady=(0, 12))

    key_var = tk.StringVar()
    entry = tk.Entry(root, textvariable=key_var, width=44, show="*")
    entry.pack(pady=4)
    entry.focus_set()

    status_label = tk.Label(root, text="", fg="#c0392b", font=("Segoe UI", 9))
    status_label.pack(pady=(4, 0))

    def open_signup():
        webbrowser.open(_GROQ_KEYS_URL)

    tk.Button(root, text="Get a free key at console.groq.com", command=open_signup).pack(
        pady=(10, 4)
    )

    def save_and_continue():
        key = key_var.get().strip()
        if not key:
            status_label.config(text="Please paste a key first.")
            return
        try:
            config.save_user_key(key)
        except OSError as exc:
            messagebox.showerror("Jarvis Setup", f"Couldn't save the key: {exc}")
            return
        root.destroy()

    tk.Button(
        root,
        text="Save & Continue",
        command=save_and_continue,
        bg="#3a4fd6",
        fg="white",
        font=("Segoe UI", 10, "bold"),
    ).pack(pady=(14, 0), ipadx=10, ipady=4)

    root.bind("<Return>", lambda _event: save_and_continue())
    root.mainloop()
