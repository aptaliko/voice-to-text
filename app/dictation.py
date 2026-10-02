"""Spoken commands: turn dictated words like «παύλα» or «κάθετος» into symbols.

Each command lists the phrases that trigger it, the text it produces and how
it attaches to its neighbours. Phrases are matched case- and accent-
insensitively, and punctuation Whisper puts around them is dropped.
"""

import re
from dataclasses import dataclass

# How a symbol sits between its neighbours.
LEFT = "left"  # "λέξη, " - glued to the previous word
RIGHT = "right"  # " (λέξη" - glued to the next word
JOIN = "join"  # "1234/2020" - glued to both
SPACED = "spaced"  # "Αθήνα - Πειραιάς"
BREAK = "break"  # line or paragraph break


@dataclass(frozen=True)
class Command:
    phrases: tuple[str, ...]
    symbol: str
    spacing: str
    capitalize_next: bool = False
    # Only convert next to a digit, for words that also have an everyday
    # meaning («κάθετος τοίχος», «πενήντα τοις εκατό» vs «50 τοις εκατό»).
    needs_digit: bool = False
    note: str = ""  # shown in the page's help


# Order matters: longer phrases first («άνω και κάτω τελεία» before «τελεία»).
COMMANDS: tuple[Command, ...] = (
    Command(("νέα παράγραφος", "νέα παράγραφο"), "\n\n", BREAK, True),
    Command(("νέα γραμμή",), "\n", BREAK, True),
    Command(("άνω και κάτω τελεία",), ":", LEFT),
    Command(("άνω τελεία",), "·", LEFT),
    Command(("άνοιγμα παρένθεσης", "ανοίγει παρένθεση", "παρένθεση ανοίγει"), "(", RIGHT),
    Command(("κλείσιμο παρένθεσης", "κλείνει παρένθεση", "παρένθεση κλείνει"), ")", LEFT),
    Command(("άνοιγμα εισαγωγικών", "ανοίγουν εισαγωγικά", "εισαγωγικά ανοίγουν"), "«", RIGHT),
    Command(("κλείσιμο εισαγωγικών", "κλείνουν εισαγωγικά", "εισαγωγικά κλείνουν"), "»", LEFT),
    Command(("παύλα",), "-", JOIN, needs_digit=True, note="1-2 ή Αθήνα - Πειραιάς"),
    Command(("παύλα",), "-", SPACED),
    Command(("κάθετος", "κάθετο"), "/", JOIN, needs_digit=True, note="δίπλα σε αριθμό: 1234/2020"),
    Command(("τοις εκατό", "τις εκατό"), "%", LEFT, needs_digit=True, note="μετά από αριθμό: 50%"),
    Command(("σύμβολο παραγράφου",), "§", SPACED),
    # Plain punctuation last, so the commands above cannot swallow it.
    Command(("τελεία",), ".", LEFT, True),
    Command(("κόμμα",), ",", LEFT),
    Command(("ερωτηματικό",), ";", LEFT, True),
    Command(("θαυμαστικό",), "!", LEFT, True),
)

_ACCENTS = {
    "α": "αά", "ε": "εέ", "η": "ηή", "ι": "ιίϊΐ", "ο": "οό", "υ": "υύϋΰ", "ω": "ωώ",
    "ά": "αά", "έ": "εέ", "ή": "ηή", "ί": "ιίϊΐ", "ό": "οό", "ύ": "υύϋΰ", "ώ": "ωώ",
    "ς": "ςσ", "σ": "σς",
}


def _fuzzy(phrase: str) -> str:
    parts = []
    for char in phrase:
        if char == " ":
            parts.append(r"\s+")
        elif char in _ACCENTS:
            parts.append(f"[{_ACCENTS[char]}]")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def _compile(command: Command) -> re.Pattern:
    words = "|".join(_fuzzy(p) for p in command.phrases)
    # Whisper often wraps a spoken command in its own commas or full stops.
    # A full stop before a line break ends the sentence, so it stays.
    before = ",?" if command.spacing == BREAK else "[,.]?"
    # Only spaces are absorbed, never line breaks made by other commands.
    core = rf"{before}[ \t]*\b(?:{words})\b[,.]?[ \t]*"
    if command.needs_digit:
        core = rf"(?:(?<=\d){core}|{core}(?=\d))"
    return re.compile(core, re.IGNORECASE)


def _replacement(command: Command) -> str:
    return {
        LEFT: f"{command.symbol} ",
        RIGHT: f" {command.symbol}",
        JOIN: command.symbol,
        SPACED: f" {command.symbol} ",
        BREAK: command.symbol,
    }[command.spacing]


_CAPITALIZE = "\x00"  # marks where the next letter must become upper case
_COMPILED = [
    (_compile(c), _replacement(c) + (_CAPITALIZE if c.capitalize_next else "")) for c in COMMANDS
]


def apply_commands(text: str) -> str:
    for pattern, replacement in _COMPILED:
        # A function, so backslashes in symbols are never treated as escapes.
        text = pattern.sub(lambda _m, r=replacement: r, text)
    text = re.sub(rf"{_CAPITALIZE}(\s*)(\w)", lambda m: m.group(1) + m.group(2).upper(), text)
    text = text.replace(_CAPITALIZE, "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"([(«]) +| +([)»,.·:;!%])", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def command_list() -> list[dict]:
    """Commands as shown in the page's help (one row per spoken phrase)."""
    rows, seen = [], set()
    for command in COMMANDS:
        if command.phrases in seen:
            continue
        seen.add(command.phrases)
        symbol = {"\n\n": "¶", "\n": "↵"}.get(command.symbol, command.symbol)
        rows.append({"say": command.phrases[0], "symbol": symbol, "note": command.note})
    return rows
