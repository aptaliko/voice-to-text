import os
from dataclasses import dataclass, field
from pathlib import Path

# Greek legal / real-estate vocabulary passed to Whisper as context.
# It nudges the model towards the right spelling of domain terms.
DEFAULT_PROMPT = (
    "Συμβόλαιο αγοραπωλησίας ακινήτου. Πωλητής, αγοραστής, συμβολαιογράφος. "
    "ΑΦΜ, ΔΟΥ, ΚΑΕΚ, Κτηματολόγιο, υποθηκοφυλακείο, οικόπεδο, διαμέρισμα, "
    "οριζόντια ιδιοκτησία, χιλιοστά εξ αδιαιρέτου. "
    # Numbers spelled out here make Whisper write them as words too, which
    # keeps the speaker's gender and case («διακοσίων πενήντα χιλιάδων»).
    "Το τίμημα ορίζεται σε διακόσιες πενήντα χιλιάδες ευρώ, εμβαδού ογδόντα πέντε τετραγωνικών μέτρων."
)


def _bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


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

    # AI spelling correction (feature flag, off by default). Needs an Ollama server.
    ai_correction: bool = field(default_factory=lambda: _bool("AI_CORRECTION"))
    ai_url: str = field(default_factory=lambda: os.getenv("AI_URL", "http://ollama:11434").rstrip("/"))
    ai_model: str = field(default_factory=lambda: os.getenv("AI_MODEL", "gemma3:12b"))
    ai_timeout: int = field(default_factory=lambda: _int("AI_TIMEOUT", 300))
    # Optional file replacing the built-in instructions (app/prompts/correction_el.md).
    ai_prompt_file: str = field(default_factory=lambda: os.getenv("AI_PROMPT_FILE", ""))

    upload_dir: Path = field(default_factory=lambda: Path(os.getenv("UPLOAD_DIR", "/tmp/voice-to-text")))
    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 200))
    # Finished jobs are forgotten after this many seconds so contract text
    # does not linger in memory.
    job_ttl_seconds: int = field(default_factory=lambda: _int("JOB_TTL_SECONDS", 3600))


settings = Settings()
