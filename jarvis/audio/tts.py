import asyncio
import base64
import json
import os
import tempfile

import edge_tts
import pygame
import requests

from .. import config

pygame.mixer.init()


async def _synthesize(text: str, path: str):
    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
    await communicate.save(path)


def _synthesize_gnani(text: str, path: str):
    """Download Timbre SSE audio to a temporary WAV, without persisting speech."""
    payload = {
        "audio_config": {
            "container": "wav", "encoding": "linear_pcm", "num_channels": 1,
            "sample_rate": 22050, "sample_width": 2,
        },
        "model": "timbre-v2.5",
        "language": config.GNANI_LANGUAGE_CODE,
        "text": text,
        "voice": config.GNANI_TTS_VOICE,
    }
    response = requests.post(
        config.GNANI_TTS_URL, json=payload,
        headers={"X-API-Key-ID": config.GNANI_API_KEY, "Content-Type": "application/json"},
        stream=True, timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"Gnani TTS returned {response.status_code}: {response.text[:1000]}"
        )
    chunks = []
    event_type = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event: "):
            event_type = line[7:].strip()
            continue
        if not line.startswith("data: "):
            continue

        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gnani TTS returned malformed SSE data") from exc

        if event_type == "error":
            raise RuntimeError(f"Gnani TTS stream error: {event.get('message', event)}")
        audio = event.get("audio")
        if audio:
            chunks.append(base64.b64decode(audio))
        event_type = ""
    if not chunks:
        raise RuntimeError("Gnani Timbre returned no audio chunks")
    with open(path, "wb") as audio:
        audio.write(b"".join(chunks))


def speak(text: str, cancel_event=None):
    """Speaks text aloud. If cancel_event is set at any point, playback stops
    immediately and this returns early (the caller keeps running)."""
    if not text:
        return

    fd, path = tempfile.mkstemp(suffix=".wav" if config.GNANI_API_KEY else ".mp3")
    os.close(fd)
    try:
        if config.GNANI_API_KEY:
            _synthesize_gnani(text, path)
        else:
            asyncio.run(_synthesize(text, path))
        if cancel_event is not None and cancel_event.is_set():
            return
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if cancel_event is not None and cancel_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(10)
    finally:
        pygame.mixer.music.unload()
        os.remove(path)
