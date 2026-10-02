import os
from dataclasses import dataclass, field
from pathlib import Path

# Greek legal / real-estate vocabulary passed to Whisper as context.
# It nudges the model towards the right spelling of domain terms.
DEFAULT_PROMPT = (
    "Συμβόλαιο αγοραπωλησίας ακινήτου. Πωλητής, αγοραστής, συμβολαιογράφος. "
    "ΑΦΜ, ΔΟΥ, ΚΑΕΚ, Κτηματολόγιο, υποθηκοφυλακείο, οικόπεδο, διαμέρισμα, "
    "οριζόντια ιδιοκτησία, χιλιοστά εξ αδιαιρέτου, τίμημα, ευρώ."
)


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    username: str = field(default_factory=lambda: os.getenv("APP_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("APP_PASSWORD", ""))

    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "large-v3-turbo"))
    whisper_compute_type: str = field(default_factory=lambda: os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
    whisper_threads: int = field(default_factory=lambda: _int("WHISPER_THREADS", 0))
    whisper_language: str = field(default_factory=lambda: os.getenv("WHISPER_LANGUAGE", "el"))
    whisper_prompt: str = field(default_factory=lambda: os.getenv("WHISPER_PROMPT", DEFAULT_PROMPT))
    model_dir: Path = field(default_factory=lambda: Path(os.getenv("MODEL_DIR", "/models")))

    ocr_languages: str = field(default_factory=lambda: os.getenv("OCR_LANGUAGES", "ell+eng"))
    ocr_dpi: int = field(default_factory=lambda: _int("OCR_DPI", 300))

    upload_dir: Path = field(default_factory=lambda: Path(os.getenv("UPLOAD_DIR", "/tmp/voice-to-text")))
    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 200))
    # Finished jobs are forgotten after this many seconds so contract text
    # does not linger in memory.
    job_ttl_seconds: int = field(default_factory=lambda: _int("JOB_TTL_SECONDS", 3600))


settings = Settings()
