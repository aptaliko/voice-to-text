"""Spoken commands: turn dictated words like «παύλα» or «κάθετος» into symbols.

Each command lists the phrases that trigger it, the text it produces and how
it attaches to its neighbours. Phrases are matched case- and accent-
insensitively, and punctuation Whisper puts around them is dropped.
"""

import re
import unicodedata
from dataclasses import dataclass

from .numbers import digits_next_to_joiners, format_numbers, normalize, single_number

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


# List numbering. Numbers need «αρίθμηση» («αρίθμηση δύο» -> "2)") so they are
# never confused with amounts, which become «δύο (2)». Letters also work with
# «παρένθεση»: «άλφα παρένθεση» -> "α)".
# Greek list letters, as Whisper spells their names. «στίγμα» is the
# traditional sixth item (στ).
_LETTER_NAMES = {
    "άλφα": "α", "βήτα": "β", "γάμα": "γ", "γάμμα": "γ", "δέλτα": "δ", "έψιλον": "ε",
    "στίγμα": "στ", "ζήτα": "ζ", "ήτα": "η", "θήτα": "θ", "γιώτα": "ι", "κάπα": "κ",
    "λάμδα": "λ", "λάμβδα": "λ", "μι": "μ", "νι": "ν", "ξι": "ξ", "όμικρον": "ο",
    "πι": "π", "ρο": "ρ", "σίγμα": "σ", "ταυ": "τ",
}
_LETTERS = {normalize(name): letter for name, letter in _LETTER_NAMES.items()}
# Single letters as Whisper may write them. «η» and «ο» are left out because
# they are also articles («η παρένθεση»).
_SINGLE_LETTERS = "αβγδεζθικλμνξπρστυφχψω"
_LETTER = rf"(?:{'|'.join(_fuzzy(w) for w in sorted(_LETTER_NAMES, key=len, reverse=True))}|στ|[{_SINGLE_LETTERS}])"
_PARENTHESIS = _fuzzy("παρένθεση")
_LETTER_ITEM = re.compile(
    rf"[,.]?[ \t]*\b(?P<marker>{_LETTER})[ \t]+{_PARENTHESIS}\b[,.]?[ \t]*", re.IGNORECASE
)
_NUMBERED_ITEM = re.compile(
    rf"[,.]?[ \t]*\b{_fuzzy('αρίθμηση')}[ \t]+(?P<words>[^\W_]+(?:[ \t]+[^\W_]+){{0,3}})", re.IGNORECASE
)
_SOFT_BREAK = "\x01"  # a line break unless one is already there


def _letter_item(match: re.Match) -> str:
    spoken = match.group("marker")
    return f"{_SOFT_BREAK}{_LETTERS.get(normalize(spoken), spoken)}) "


def _numbered_item(match: re.Match) -> str:
    words = match.group("words").split()
    # Use the longest leading run of words that is one number or one letter.
    for count in range(len(words), 0, -1):
        spoken = " ".join(words[:count])
        if spoken.isdigit():
            marker = spoken
        elif normalize(spoken) in _LETTERS or (count == 1 and len(spoken) <= 2 and spoken.isalpha()):
            marker = _LETTERS.get(normalize(spoken), spoken)
        else:
            value = single_number(words[:count])
            if value is None:
                continue
            marker = str(value)
        rest = words[count:]
        if rest and normalize(rest[0]).rstrip(".,") == normalize("παρένθεση"):
            rest = rest[1:]
        return f"{_SOFT_BREAK}{marker}) " + " ".join(rest)
    return match.group()


_CAPITALIZE = "\x00"  # marks where the next letter must become upper case
_COMPILED = [
    (_compile(c), _replacement(c) + (_CAPITALIZE if c.capitalize_next else "")) for c in COMMANDS
]


# «κεφαλαία γράμματα» … «μικρά γράμματα» writes the words in between in capitals.
# The full phrase is required: «κεφαλαία» alone also means capital (funds).
_CAPS_ON, _CAPS_OFF = "\x03", "\x04"
_CAPS_COMMANDS = [
    (re.compile(rf",?[ \t]*\b{_fuzzy(phrase)}\b[,.]?[ \t]*", re.IGNORECASE), f" {marker}")
    for phrase, marker in (("κεφαλαία γράμματα", _CAPS_ON), ("μικρά γράμματα", _CAPS_OFF))
]


def _upper(text: str) -> str:
    """Greek capitals: no accent (tonos), but the diaeresis stays (ΠΡΩΤΕΪΝΗ)."""
    decomposed = unicodedata.normalize("NFD", text.upper()).replace("\u0301", "")
    return unicodedata.normalize("NFC", decomposed)


def _apply_caps(text: str) -> str:
    out, caps = [], False
    for part in re.split(f"([{_CAPS_ON}{_CAPS_OFF}])", text):
        if part in (_CAPS_ON, _CAPS_OFF):
            caps = part == _CAPS_ON
        else:
            out.append(_upper(part) if caps else part)
    return "".join(out)


def apply_commands(text: str) -> str:
    for pattern, marker in _CAPS_COMMANDS:
        text = pattern.sub(marker, text)
    text = _NUMBERED_ITEM.sub(_numbered_item, text)
    text = _LETTER_ITEM.sub(_letter_item, text)
    text = digits_next_to_joiners(text)
    for pattern, replacement in _COMPILED:
        # A function, so backslashes in symbols are never treated as escapes.
        text = pattern.sub(lambda _m, r=replacement: r, text)
    text = format_numbers(text)
    text = re.sub(rf"{_CAPITALIZE}(\s*)(\w)", lambda m: m.group(1) + m.group(2).upper(), text)
    text = text.replace(_CAPITALIZE, "")
    text = _apply_caps(text)
    # Each list item starts on its own line, without doubling an existing break.
    text = re.sub(rf"\s*{_SOFT_BREAK}", lambda m: m.group(0)[:-1] if "\n" in m.group(0) else "\n", text)
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
    rows.append({"say": "κεφαλαία γράμματα", "symbol": "ΑΒΓ", "note": "μέχρι «μικρά γράμματα»"})
    rows.append({"say": "μικρά γράμματα", "symbol": "αβγ", "note": "επιστροφή σε πεζά"})
    rows.append({"say": "αρίθμηση ένα", "symbol": "1)", "note": "αρίθμηση σε νέα γραμμή"})
    rows.append({"say": "άλφα παρένθεση", "symbol": "α)", "note": "ή «αρίθμηση άλφα» · βήτα, γάμα, … στίγμα (στ)"})
    rows.append({"say": "είκοσι εννέα", "symbol": "… (29)", "note": "ολογράφως και αριθμητικά: είκοσι εννέα (29)"})
    rows.append({"say": "ογδόντα πέντε τετραγωνικά μέτρα", "symbol": "… (85 τ.μ.)", "note": "και «85 τ.μ.» → ολογράφως"})
    rows.append({"say": "άνοιγμα παρένθεσης δύο κλείσιμο παρένθεσης", "symbol": "(2)", "note": "μόνο ο αριθμός"})
    return rows
