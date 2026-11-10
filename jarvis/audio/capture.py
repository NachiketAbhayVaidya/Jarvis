"""Short-lived microphone captures used by Gnani APIs.

Audio is written only to a temporary file and callers must delete it after the
network request. Voiceprints stay with Gnani's biometric service, not here.
"""
import os
import tempfile
import wave

import sounddevice as sd

SAMPLE_RATE = 16_000


def record_wav(duration_seconds: float) -> str:
    """Record mono PCM16 audio and return a temporary WAV pathname."""
    frames = sd.rec(
        int(duration_seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
        channels=1, dtype="int16"
    )
    sd.wait()
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(frames.tobytes())
    return path
