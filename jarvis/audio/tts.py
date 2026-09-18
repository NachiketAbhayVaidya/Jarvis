import asyncio
import os
import tempfile

import edge_tts
import pygame

from .. import config

pygame.mixer.init()


async def _synthesize(text: str, path: str):
    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
    await communicate.save(path)


def speak(text: str, cancel_event=None):
    """Speaks text aloud. If cancel_event is set at any point, playback stops
    immediately and this returns early (the caller keeps running)."""
    if not text:
        return

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
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
