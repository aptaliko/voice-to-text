"""Speech-to-text with faster-whisper, running locally on CPU."""

import re
import threading
from pathlib import Path

from .config import settings
from .jobs import ProgressFn

# A pause this long (seconds) between segments starts a new paragraph.
PARAGRAPH_PAUSE = 2.5

# Spoken formatting commands. Accents are optional because Whisper is not
# always consistent with them.
_COMMANDS = [
    (re.compile(r",?\s*\bν[εέ]α\s+παρ[αά]γραφο[ςσ]?\b[.,]?\s*", re.IGNORECASE), "\n\n"),
    (re.compile(r",?\s*\bν[εέ]α\s+γραμμ[ηή]\b[.,]?\s*", re.IGNORECASE), "\n"),
]

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(
                settings.whisper_model,
                device="cpu",
                compute_type=settings.whisper_compute_type,
                cpu_threads=settings.whisper_threads,
                download_root=str(settings.model_dir),
            )
        return _model


def apply_commands(text: str) -> str:
    for pattern, replacement in _COMMANDS:
        text = pattern.sub(replacement, text)
    # Capitalise the first letter after a forced break.
    text = re.sub(r"(\n+)(\w)", lambda m: m.group(1) + m.group(2).upper(), text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def join_segments(segments: list[tuple[float, float, str]]) -> str:
    """Join (start, end, text) segments, breaking paragraphs on long pauses."""
    parts: list[str] = []
    last_end = None
    for start, end, text in segments:
        text = text.strip()
        if not text:
            continue
        if last_end is not None:
            parts.append("\n\n" if start - last_end >= PARAGRAPH_PAUSE else " ")
        parts.append(text)
        last_end = end
    return apply_commands("".join(parts))


def transcribe(path: Path, progress: ProgressFn) -> str:
    model = _get_model()
    segments, info = model.transcribe(
        str(path),
        language=settings.whisper_language or None,
        initial_prompt=settings.whisper_prompt or None,
        beam_size=5,
        vad_filter=True,
    )
    collected = []
    for segment in segments:
        collected.append((segment.start, segment.end, segment.text))
        if info.duration:
            progress(segment.end / info.duration)
    return join_segments(collected)
