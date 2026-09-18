import queue

import sounddevice as sd
from openwakeword.model import Model
from openwakeword.utils import download_models

from .. import config

_SAMPLE_RATE = 16000
_FRAME_SAMPLES = 1280  # 80ms at 16kHz, openWakeWord's expected chunk size

_model = None


def _get_model():
    global _model
    if _model is None:
        download_models(model_names=[config.WAKE_WORD_MODEL])
        _model = Model(wakeword_models=[config.WAKE_WORD_MODEL])
    return _model


def wait_for_wakeword(stop_event):
    """Blocks until the configured wake word is detected, or stop_event is set."""
    model = _get_model()
    model.reset()
    audio_queue = queue.Queue()

    def _callback(indata, frames, time_info, status):
        audio_queue.put(indata[:, 0].copy())

    with sd.InputStream(
        samplerate=_SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=_FRAME_SAMPLES,
        callback=_callback,
    ):
        while not stop_event.is_set():
            try:
                frame = audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            predictions = model.predict(frame)
            score = predictions.get(config.WAKE_WORD_MODEL, 0.0)
            if score >= config.WAKE_WORD_THRESHOLD:
                return True

    return False
