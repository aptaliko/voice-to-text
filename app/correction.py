"""Optional AI spelling correction with a local model served by Ollama.

The model only *suggests* a corrected text. A change is kept only when the
new word sounds exactly like the old one («η γνωστή» -> «οι γνωστοί»), so the
model cannot rephrase, add or drop words, or touch numbers, names and
punctuation. Everything runs on the local Ollama server; nothing leaves it.
"""

import json
import re
import unicodedata
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from .config import settings
from .jobs import ProgressFn
from .numbers import normalize

DEFAULT_PROMPT_FILE = Path(__file__).parent / "prompts" / "correction_el.md"

_WORD = re.compile(r"[^\W\d_]+")

# Pronunciation key: letters and digraphs that sound the same map to one symbol.
_DIGRAPHS = [
    ("ου", "u"), ("αυ", "av"), ("ευ", "ev"), ("ηυ", "iv"),
    ("ει", "i"), ("οι", "i"), ("υι", "i"), ("αι", "e"), ("γγ", "γκ"),
]
_LETTERS = str.maketrans({"η": "i", "ι": "i", "υ": "i", "ω": "o", "ο": "o", "ε": "e", "α": "a", "β": "v"})
# Words whose final ν is a spelling rule, not a different word.
_FINAL_NU = {normalize(w) for w in ("την", "στην", "μην", "δεν", "αυτήν", "καμιάν", "σαν")}


def sound(word: str) -> str:
    """How a Greek word sounds, ignoring spelling: sound("οι") == sound("η")."""
    key = normalize(word)
    if key in _FINAL_NU:
        key = key[:-1]
    for digraph, replacement in _DIGRAPHS:
        key = key.replace(digraph, replacement)
    key = key.translate(_LETTERS)
    return re.sub(r"(.)\1+", r"\1", key)  # double consonants sound single


def _match_case(original: str, new: str) -> str:
    if original.isupper() and len(original) > 1:
        # Greek capitals are written without accents.
        return "".join(c for c in unicodedata.normalize("NFD", new.upper()) if unicodedata.category(c) != "Mn")
    if original[:1].isupper():
        return new[:1].upper() + new[1:]
    return new[:1].lower() + new[1:]


def apply_safe_changes(original: str, suggestion: str) -> tuple[str, list[dict]]:
    """Apply only the suggested word changes that sound identical to the original.

    The texts are aligned by sound, so a homophone fix counts as "the same
    word" and anything else (added, removed or different words) is ignored.
    """
    words = list(_WORD.finditer(original))
    old = [m.group() for m in words]
    new = _WORD.findall(suggestion)
    matcher = SequenceMatcher(a=[sound(w) for w in old], b=[sound(w) for w in new], autojunk=False)
    if matcher.ratio() < 0.6:
        return original, []  # the model rewrote the text; ignore it entirely

    replacements: dict[int, str] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset in range(i2 - i1):
            before, after = old[i1 + offset], new[j1 + offset]
            if before.lower() == after.lower():
                continue
            if before.isupper() and normalize(before) == normalize(after):
                continue  # only an accent, which capitals don't carry
            replacements[i1 + offset] = _match_case(before, after)

    out, last, changes = [], 0, []
    for index, match in enumerate(words):
        if index in replacements:
            out += [original[last:match.start()], replacements[index]]
            last = match.end()
            context = " ".join(replacements.get(i, old[i]) for i in range(max(0, index - 2), min(len(old), index + 3)))
            changes.append({"from": old[index], "to": replacements[index], "context": context})
    return "".join(out) + original[last:], changes


class CorrectionError(RuntimeError):
    pass


def _prompt() -> str:
    path = Path(settings.ai_prompt_file) if settings.ai_prompt_file else DEFAULT_PROMPT_FILE
    return path.read_text(encoding="utf-8")


def _request(path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{settings.ai_url}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or settings.ai_timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise CorrectionError(f"Ο διακομιστής AI απάντησε {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CorrectionError(f"Δεν βρέθηκε ο διακομιστής AI στο {settings.ai_url} ({exc})") from exc


def _clean_reply(reply: str) -> str:
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL)  # reasoning models
    reply = re.sub(r"^\s*(Έξοδος|Διορθωμένο κείμενο)\s*:\s*", "", reply.strip(), flags=re.IGNORECASE)
    return reply.strip().strip("«»\"'")


def suggest(text: str) -> str:
    """Ask the model for a corrected version of one paragraph."""
    reply = _request(
        "/api/chat",
        {
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": _prompt()},
                {"role": "user", "content": f"Είσοδος: {text}"},
            ],
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0},
        },
    )
    return _clean_reply(reply.get("message", {}).get("content", ""))


def correct_text(text: str, progress: ProgressFn | None = None) -> dict:
    """Correct paragraph by paragraph. On failure the text is returned unchanged with a warning."""
    lines = text.split("\n")
    todo = [i for i, line in enumerate(lines) if _WORD.search(line)]
    corrections: list[dict] = []
    try:
        for done, index in enumerate(todo, start=1):
            lines[index], changes = apply_safe_changes(lines[index], suggest(lines[index]))
            corrections += changes
            if progress:
                progress(done / len(todo))
    except CorrectionError as exc:
        return {"text": text, "original": text, "corrections": [], "warning": f"Η διόρθωση AI παραλείφθηκε: {exc}"}
    return {"text": "\n".join(lines), "original": text, "corrections": corrections}


def status() -> dict:
    """Feature flag plus whether the Ollama server and model are reachable."""
    info = {"enabled": settings.ai_correction, "model": settings.ai_model, "reachable": False, "installed": False}
    if not settings.ai_correction:
        return info
    try:
        tags = _request("/api/tags", timeout=3)
    except CorrectionError as exc:
        info["error"] = str(exc)
        return info
    info["reachable"] = True
    names = {m.get("name", "") for m in tags.get("models", [])}
    wanted = settings.ai_model if ":" in settings.ai_model else f"{settings.ai_model}:latest"
    info["installed"] = wanted in names or settings.ai_model in names
    if not info["installed"]:
        info["error"] = f"Το μοντέλο {settings.ai_model} δεν είναι εγκατεστημένο. Τρέξτε: ollama pull {settings.ai_model}"
    return info
