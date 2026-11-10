# Building Jarvis.exe for distribution

## Prerequisites

```
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

## Build

```
pyinstaller Jarvis.spec --noconfirm --clean
```

(First time, or if you change dependencies, you can regenerate the spec instead:)

```
pyinstaller --onedir --windowed --name Jarvis ^
  --collect-all openwakeword ^
  --collect-all sounddevice ^
  --collect-all edge_tts ^
  --collect-all pystray ^
  --collect-all onnxruntime ^
  --collect-all pyaudio ^
  --noconfirm --clean ^
  main.py
```

This produces `dist\Jarvis\` (a folder, ~280MB) containing `Jarvis.exe` plus its
`_internal` dependencies. `--onedir` (a folder) is used instead of `--onefile`
(a single .exe) because onefile re-extracts everything into a temp folder on
*every* launch, which adds 30-40 seconds of silent startup delay before any
window appears — that looks broken to someone who doesn't know to expect it.
Onedir starts in a few seconds instead.

## Distributing

Zip the whole `dist\Jarvis\` folder and send that. Recipients:

1. Unzip it anywhere.
2. Double-click `Jarvis.exe` inside the folder.
3. First launch shows a small setup window asking for a free Groq API key
   (with a button linking to https://console.groq.com/keys) — they paste
   their own key and click Save & Continue. This is saved to
   `%APPDATA%\Jarvis\.env` and only needs to happen once per machine.
4. After that, Jarvis runs the same way it does for you: say "Hey Jarvis" to
   wake it, a small floating bubble in the bottom-right shows status, double-tap
   the bubble to interrupt a response, triple-tap to quit.

Note: the first few seconds after wake-word detection starts working may be
slightly slow the very first time, since openWakeWord loads its models into
memory on first use — this is normal and only noticeable once per launch.

## Rebuilding after code changes

Just re-run the `pyinstaller Jarvis.spec --noconfirm --clean` command above —
it picks up any changes to the Python source automatically.

## Remote Access (control Jarvis from your phone)

Jarvis runs a small local web server so you can send it commands, watch its
status/transcript live, and trigger skills directly from your phone.

1. Install [Tailscale](https://tailscale.com/download) on this PC and on your
   phone, and sign in to the same account on both (free for personal use).
2. Launch Jarvis normally. On first run it silently generates a pairing token
   into `%APPDATA%\Jarvis\.env` — nothing to configure.
3. Right-click the Jarvis tray icon → **Remote Access...** to see a QR code,
   your Tailscale IP/port, and the pairing token.
4. Scan the QR code with your phone (on the same tailnet) — it opens the
   Jarvis web app and pairs automatically. Use your browser's "Add to Home
   Screen" option to install it like an app.

If Tailscale isn't detected, the same window falls back to your local network
address instead — that only works while your phone is on the same Wi-Fi.
