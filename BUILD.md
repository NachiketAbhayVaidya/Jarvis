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
