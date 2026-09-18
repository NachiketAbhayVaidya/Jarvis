import speech_recognition as sr

_recognizer = sr.Recognizer()
_recognizer.energy_threshold = 300
_recognizer.pause_threshold = 0.6
_recognizer.dynamic_energy_threshold = False


def listen_for_command(timeout=5):
    """Captures one spoken command from the microphone and transcribes it.

    Returns the transcribed text, or None if nothing was understood in time.
    """
    with sr.Microphone() as source:
        try:
            audio = _recognizer.listen(source, timeout=timeout)
        except sr.WaitTimeoutError:
            return None

    try:
        return _recognizer.recognize_google(audio)
    except (sr.UnknownValueError, sr.RequestError):
        return None
