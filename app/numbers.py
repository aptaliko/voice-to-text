"""Contract-style numbers: «είκοσι εννέα (29)», «διακόσιες πενήντα χιλιάδες ευρώ (250.000 €)».

Numbers said in words keep the speaker's words (with their gender and case)
and get the digits appended. Numbers Whisper wrote as digits get the words
generated in front of them. Identifiers, dates, references like «άρθρο 5»
and numbers in parentheses are left as digits.
"""

import re
import unicodedata


def normalize(word: str) -> str:
    """Lower case, no accents, final sigma as σ: for matching only."""
    stripped = "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")
    return stripped.lower().replace("ς", "σ")


# ---------- words -> value ----------

UNIT, TEEN, TEN, HUNDRED, THOUSAND_ALONE, THOUSANDS, MILLIONS = range(7)

_WORDS: dict[str, tuple[int, int]] = {}


def _add(kind: int, value: int, *forms: str) -> None:
    for form in forms:
        _WORDS[normalize(form)] = (value, kind)


_add(UNIT, 1, "ένα", "ένας", "μία", "μια", "ενός", "μιας", "μίας")
_add(UNIT, 2, "δύο", "δυο")
_add(UNIT, 3, "τρία", "τρεις", "τριών")
_add(UNIT, 4, "τέσσερα", "τέσσερις", "τεσσάρων")
_add(UNIT, 5, "πέντε")
_add(UNIT, 6, "έξι")
_add(UNIT, 7, "επτά", "εφτά")
_add(UNIT, 8, "οκτώ", "οχτώ")
_add(UNIT, 9, "εννέα", "εννιά")
_add(TEN, 10, "δέκα")
_add(TEEN, 11, "έντεκα", "ένδεκα")
_add(TEEN, 12, "δώδεκα")
_add(TEEN, 13, "δεκατρία", "δεκατρείς", "δεκατριών")
_add(TEEN, 14, "δεκατέσσερα", "δεκατέσσερις", "δεκατεσσάρων")
_add(TEEN, 15, "δεκαπέντε")
_add(TEEN, 16, "δεκαέξι", "δεκάξι")
_add(TEEN, 17, "δεκαεπτά", "δεκαεφτά")
_add(TEEN, 18, "δεκαοκτώ", "δεκαοχτώ")
_add(TEEN, 19, "δεκαεννέα", "δεκαεννιά")
for _value, _word in enumerate(
    ["είκοσι", "τριάντα", "σαράντα", "πενήντα", "εξήντα", "εβδομήντα", "ογδόντα", "ενενήντα"], start=2
):
    _add(TEN, _value * 10, _word)
_add(HUNDRED, 100, "εκατό", "εκατόν")
for _value, _stems in {
    2: ["διακοσι"], 3: ["τριακοσι"], 4: ["τετρακοσι"], 5: ["πεντακοσι"], 6: ["εξακοσι"],
    7: ["επτακοσι", "εφτακοσι"], 8: ["οκτακοσι", "οχτακοσι"], 9: ["εννιακοσι", "εννεακοσι"],
}.items():
    for _stem in _stems:
        _add(HUNDRED, _value * 100, *(_stem + ending for ending in ("α", "ες", "οι", "ων", "ουσ")))
_add(THOUSAND_ALONE, 1000, "χίλια", "χίλιες", "χίλιοι", "χιλίων")
_add(THOUSANDS, 1000, "χιλιάδα", "χιλιάδες", "χιλιάδων")
_add(MILLIONS, 1_000_000, "εκατομμύριο", "εκατομμύρια", "εκατομμυρίου", "εκατομμυρίων")

# Order of the parts inside a group below a thousand.
_RANK = {HUNDRED: 3, TEN: 2, TEEN: 1, UNIT: 0}


def word_value(word: str) -> int | None:
    entry = _WORDS.get(normalize(word))
    return entry[0] if entry else None


class _Parser:
    """Splits a run of number words into numbers, e.g. «δύο τρία» -> 2, 3."""

    def __init__(self):
        self.numbers: list[tuple[int, int, int]] = []  # (first token, last token, value)
        self._reset(None)

    def _reset(self, start):
        self.start, self.end = start, None
        self.total, self.current = 0, 0
        self.rank, self.after_ten = None, False
        self.scale = float("inf")

    def _close(self):
        if self.start is not None and self.end is not None:
            self.numbers.append((self.start, self.end, self.total + self.current))
        self._reset(None)

    def _accepts(self, kind: int) -> bool:
        if kind in _RANK:
            if self.rank is None:
                return True
            if self.after_ten and kind == TEEN:
                return False
            return _RANK[kind] < self.rank
        if kind == THOUSAND_ALONE:
            return self.current == 0 and self.scale > 1000
        if kind == THOUSANDS:
            return self.current > 0 and self.scale > 1000
        return self.current > 0 and self.scale > 1_000_000  # MILLIONS

    def feed(self, index: int, value: int, kind: int) -> None:
        if self.start is None or not self._accepts(kind):
            self._close()
            self._reset(index)
            if not self._accepts(kind):  # e.g. a lone «χιλιάδες»
                self._reset(None)
                return
        self.end = index
        if kind in _RANK:
            self.current += value
            self.rank, self.after_ten = _RANK[kind], kind == TEN
        elif kind == THOUSAND_ALONE:
            self.total += 1000
            self.scale, self.rank = 1000, None
        else:
            self.total += self.current * value
            self.current, self.scale, self.rank = 0, value, None

    def finish(self) -> list[tuple[int, int, int]]:
        self._close()
        return self.numbers


def single_number(words: list[str]) -> int | None:
    """The value if the words form exactly one number, else None."""
    parser = _Parser()
    for index, word in enumerate(words):
        entry = _WORDS.get(normalize(word))
        if entry is None:
            return None
        parser.feed(index, *entry)
    numbers = parser.finish()
    if len(numbers) == 1 and numbers[0][:2] == (0, len(words) - 1):
        return numbers[0][2]
    return None


# ---------- value -> words ----------

_UNITS = {
    # value: (neuter, feminine, neuter genitive, feminine genitive)
    1: ("ένα", "μία", "ενός", "μίας"),
    3: ("τρία", "τρεις", "τριών", "τριών"),
    4: ("τέσσερα", "τέσσερις", "τεσσάρων", "τεσσάρων"),
    13: ("δεκατρία", "δεκατρείς", "δεκατριών", "δεκατριών"),
    14: ("δεκατέσσερα", "δεκατέσσερις", "δεκατεσσάρων", "δεκατεσσάρων"),
}
_PLAIN = {
    2: "δύο", 5: "πέντε", 6: "έξι", 7: "επτά", 8: "οκτώ", 9: "εννέα", 10: "δέκα", 11: "έντεκα",
    12: "δώδεκα", 15: "δεκαπέντε", 16: "δεκαέξι", 17: "δεκαεπτά", 18: "δεκαοκτώ", 19: "δεκαεννέα",
    20: "είκοσι", 30: "τριάντα", 40: "σαράντα", 50: "πενήντα", 60: "εξήντα", 70: "εβδομήντα",
    80: "ογδόντα", 90: "ενενήντα",
}
_HUNDREDS = {
    # value: (nominative stem, genitive)
    2: ("διακόσι", "διακοσίων"), 3: ("τριακόσι", "τριακοσίων"), 4: ("τετρακόσι", "τετρακοσίων"),
    5: ("πεντακόσι", "πεντακοσίων"), 6: ("εξακόσι", "εξακοσίων"), 7: ("επτακόσι", "επτακοσίων"),
    8: ("οκτακόσι", "οκτακοσίων"), 9: ("εννιακόσι", "εννιακοσίων"),
}


def _small(n: int, feminine: bool, genitive: bool) -> str:
    if n in _UNITS:
        return _UNITS[n][feminine + 2 * genitive]
    return _PLAIN[n]


def _below_thousand(n: int, feminine: bool = False, genitive: bool = False) -> list[str]:
    words = []
    hundreds, rest = divmod(n, 100)
    if hundreds == 1:
        words.append("εκατόν" if rest else "εκατό")
    elif hundreds:
        stem, gen = _HUNDREDS[hundreds]
        words.append(gen if genitive else stem + ("ες" if feminine else "α"))
    if 10 <= rest < 20 or rest in _UNITS or rest < 10:
        if rest:
            words.append(_small(rest, feminine, genitive))
    else:
        tens, unit = divmod(rest, 10)
        words.append(_PLAIN[tens * 10])
        if unit:
            words.append(_small(unit, feminine, genitive))
    return words


def to_words(n: int, genitive: bool = False) -> str:
    """Neuter Greek words for n (genitive after «των»)."""
    if n == 0:
        return "μηδέν"
    millions, rest = divmod(n, 1_000_000)
    thousands, rest = divmod(rest, 1000)
    words = []
    if millions == 1:
        words += ["ενός εκατομμυρίου"] if genitive else ["ένα εκατομμύριο"]
    elif millions:
        words += _below_thousand(millions, False, genitive) + ["εκατομμυρίων" if genitive else "εκατομμύρια"]
    if thousands == 1:
        words.append("χιλίων" if genitive else "χίλια")
    elif thousands:
        words += _below_thousand(thousands, True, genitive) + ["χιλιάδων" if genitive else "χιλιάδες"]
    words += _below_thousand(rest, False, genitive)
    return " ".join(words)


def format_digits(n: int, grouped: bool) -> str:
    return f"{n:,}".replace(",", ".") if grouped else str(n)


# ---------- text rewriting ----------

# After these words a number is a reference, not a quantity, so it is written in digits.
_REFERENCE_WORDS = {
    normalize(w)
    for w in (
        "άρθρο", "άρθρου", "άρθρα", "άρθρων", "παρ", "παράγραφος", "παράγραφο", "παραγράφου",
        "αρ", "αριθ", "αριθμ", "αριθμός", "αριθμό", "αριθμού", "ν", "νόμος", "νόμο", "νόμου",
        "ΦΕΚ", "ΑΦΜ", "ΚΑΕΚ", "ΑΔΤ", "τηλ", "τηλέφωνο", "ΤΚ", "§",
        "σελίδα", "σελ", "φύλλο", "τόμος", "τόμου",
    )
}
_WORD = re.compile(r"[^\W\d_]+|§")
_EURO = re.compile(r"[ \t]+ευρώ\b|[ \t]*€", re.IGNORECASE)
_PERCENT = re.compile(r"[ \t]+τ[οι]{1,2}ς[ \t]+εκατ[οό]\b|[ \t]*%", re.IGNORECASE)
# Square metres, spoken («τετραγωνικά μέτρα», «τετραγωνικών μέτρων», «τετραγωνικά») or abbreviated («τ.μ.», «m²»).
_SQM_WORDS = re.compile(
    r"[ \t]+τετραγωνικ(?:[αά]|[οό]|[ωώ]ν|[οό]ύ|ου)(?:[ \t]+μ[εέ]τρ(?:α|ο|ων|ου))?(?!\w)", re.IGNORECASE
)
_SQM_SHORT = re.compile(r"[ \t]*(?:τ\.?[ \t]?μ\.?(?!\w)|m2(?!\w)|m²)", re.IGNORECASE)
# After these words a generated number is in the genitive: «εμβαδού ογδόντα πέντε τετραγωνικών μέτρων».
_GENITIVE_BEFORE = {
    normalize(w)
    for w in ("των", "εμβαδού", "επιφανείας", "εκτάσεως", "έκτασης", "αντί", "ποσού", "τιμήματος", "αξίας", "ύψους")
}
_JOINER_WORDS = re.compile(r"^[ \t]*(?:κ[αά]θετο[ςσ]?|π[αά]ύλα|π[αά]υλα)\b", re.IGNORECASE)
_JOINER_WORDS_BEFORE = re.compile(r"\b(?:κ[αά]θετο[ςσ]?|π[αά]ύλα|π[αά]υλα)[ \t]*$", re.IGNORECASE)


def _previous_word(text: str, position: int) -> str:
    match = re.search(r"([^\W\d_]+|§)[.\s]*$", text[:position])
    return normalize(match.group(1)) if match else ""


# A street number follows the street name: «οδού Πατησίων 25», «Λεωφόρου Βασιλίσσης Σοφίας 12».
_STREET_WORDS = {
    normalize(w)
    for w in ("οδός", "οδό", "οδού", "λεωφόρος", "λεωφόρο", "λεωφόρου", "λεωφ", "πλατεία", "πλατείας", "πάροδος", "παρόδου")
}


def _is_reference(text: str, position: int) -> bool:
    if _previous_word(text, position) in _REFERENCE_WORDS:
        return True
    # Up to three words back, within the same clause.
    clause = re.split(r"[,;:·()\n]", text[:position])[-1]
    return any(normalize(w) in _STREET_WORDS for w in re.findall(r"[^\W\d_]+", clause)[-4:])


def _number_runs(text: str):
    """Yield (start, end, value) for each number said in words."""
    tokens = []
    for match in _WORD.finditer(text):
        entry = _WORDS.get(normalize(match.group()))
        previous = normalize(tokens[-1][0].group()) if tokens else ""
        # «τοις εκατό» is a percentage, not a hundred.
        if entry and entry[1] == HUNDRED and previous in ("τοισ", "τισ"):
            entry = None
        tokens.append((match, entry))
    run: list[tuple[re.Match, tuple[int, int]]] = []

    def flush():
        if not run:
            return
        parser = _Parser()
        for index, (_, (value, kind)) in enumerate(run):
            parser.feed(index, value, kind)
        for first, last, value in parser.finish():
            yield run[first][0].start(), run[last][0].end(), value, last - first + 1

    for match, entry in tokens:
        if entry and (not run or text[run[-1][0].end():match.start()].strip(" \t") == ""):
            run.append((match, entry))
            continue
        yield from flush()
        run = [(match, entry)] if entry else []
    yield from flush()


def digits_next_to_joiners(text: str) -> str:
    """«χίλια κάθετος δύο χιλιάδες» -> «1000 κάθετος 2000», so «κάθετος»/«παύλα» can join them."""
    out, last = [], 0
    for start, end, value, _ in list(_number_runs(text)):
        if _JOINER_WORDS.match(text[end:]) or _JOINER_WORDS_BEFORE.search(text[:start]):
            out += [text[last:start], str(value)]
            last = end
    return "".join(out) + text[last:]


def _unit(after: str) -> re.Match | None:
    return _EURO.match(after) or _PERCENT.match(after) or _SQM_WORDS.match(after) or _SQM_SHORT.match(after)


def _with_unit(words: str, value: int, after: str, genitive: bool = False, grouped: bool = False) -> tuple[str, int]:
    """Words plus digits in parentheses, moving a following unit inside them."""
    if match := _EURO.match(after):
        return f"{words} ευρώ ({format_digits(value, True)} €)", match.end()
    if match := _PERCENT.match(after):
        unit = match.group().strip()
        return f"{words} {'τοις εκατό' if unit == '%' else unit} ({format_digits(value, grouped)}%)", match.end()
    if match := _SQM_WORDS.match(after) or _SQM_SHORT.match(after):
        unit = match.group().strip()
        if _SQM_SHORT.fullmatch(match.group()):
            if value == 1:
                unit = "τετραγωνικού μέτρου" if genitive else "τετραγωνικό μέτρο"
            else:
                unit = "τετραγωνικών μέτρων" if genitive else "τετραγωνικά μέτρα"
        return f"{words} {unit} ({format_digits(value, value >= 1000)} τ.μ.)", match.end()
    return f"{words} ({format_digits(value, grouped)})", 0


def _format_word_numbers(text: str) -> str:
    out, last = [], 0
    for start, end, value, count in list(_number_runs(text)):
        if count == 1 and value == 1:
            continue  # «ένα», «μία» are usually the article
        before, after = text[:start], text[end:]
        if re.search(r"\([ \t]*$", before) and re.match(r"[ \t]*\)", after):
            replacement, consumed = format_digits(value, value >= 10000), 0  # explicit «(2)»
        elif _is_reference(text, start):
            replacement, consumed = str(value), 0  # «άρθρο πέντε» -> «άρθρο 5»
        elif re.match(r"[ \t]*\(", after[unit.end():] if (unit := _unit(after)) else after):
            continue  # already followed by its digits
        else:
            replacement, consumed = _with_unit(text[start:end], value, after, grouped=value >= 10000)
        out += [text[last:start], replacement]
        last = end + consumed
    return "".join(out) + text[last:]


_DIGITS = re.compile(r"(?<![\w/.,:\-(§])(\d{1,3}(?:\.\d{3})+|0|[1-9]\d{0,3})(?![\w/:\-)]|[.,]\d)")


def _format_digit_numbers(text: str) -> str:
    out, last = [], 0
    for match in _DIGITS.finditer(text):
        start, end = match.span()
        if _is_reference(text, start):
            continue
        previous = _previous_word(text, start)
        value = int(match.group().replace(".", ""))
        after = text[end:]
        genitive = previous in _GENITIVE_BEFORE
        words = to_words(value, genitive=genitive)
        replacement, consumed = _with_unit(words, value, after, genitive, grouped="." in match.group())
        out += [text[last:start], replacement]
        last = end + consumed
    return "".join(out) + text[last:]


def format_numbers(text: str) -> str:
    return _format_digit_numbers(_format_word_numbers(text))
