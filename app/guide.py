"""The dictation dictionary shown in the page («Λεξικό υπαγόρευσης»).

It is built from the same rules the app uses, and every example's result is
produced by running the real dictation rules on it, so the page always shows
what the app actually writes. tests/test_guide.py fails if a voice command
exists that the dictionary does not mention.

When you add or change a dictation rule, add or update its entry here.
"""

from .dictation import (
    BREAK,
    CAPS_OFF_PHRASE,
    CAPS_ON_PHRASE,
    COMMANDS,
    LETTER_NAMES,
    apply_commands,
)

# One or more spoken examples per symbol of COMMANDS.
_SYMBOL_EXAMPLES = {
    ".": ["ο πωλητής δηλώνει τελεία ο αγοραστής αποδέχεται"],
    ",": ["ο πωλητής κόμμα κάτοικος Αθηνών"],
    ":": ["ο αγοραστής άνω κάτω τελεία Γεώργιος Παπαδόπουλος"],
    "·": ["ο πωλητής δηλώνει άνω τελεία ο αγοραστής αποδέχεται"],
    ";": ["είναι αληθές ερωτηματικό"],
    "!": ["προσοχή θαυμαστικό"],
    "(": ["ο πωλητής άνοιγμα παρένθεσης εφεξής πωλητής κλείσιμο παρένθεσης δηλώνει"],
    ")": ["ο πωλητής άνοιγμα παρένθεσης εφεξής πωλητής κλείσιμο παρένθεσης δηλώνει"],
    "«": ["ο όρος άνοιγμα εισαγωγικών ως έχει κλείσιμο εισαγωγικών"],
    "»": ["ο όρος άνοιγμα εισαγωγικών ως έχει κλείσιμο εισαγωγικών"],
    "-": ["ΚΑΕΚ 05 παύλα 001 παύλα 23", "Αθήνα παύλα Πειραιάς"],
    "/": ["συμβόλαιο 1234 κάθετος 2020"],
    "%": ["ποσοστό 50 τοις εκατό"],
    "§": ["σύμφωνα με το σύμβολο παραγράφου 3"],
}

_SYMBOL_NOTES = {
    "-": "Ανάμεσα σε αριθμούς κολλάει (05-001)· ανάμεσα σε λέξεις μπαίνει με κενά.",
    "/": "Μόνο δίπλα σε αριθμό· αλλιώς η λέξη «κάθετος» μένει όπως είναι.",
    "%": "Μόνο μετά από αριθμό· το ποσοστό γράφεται ολογράφως και αριθμητικά.",
    ":": "Λέγεται με ή χωρίς «και».",
}


def _row(written: str, say: list[str], examples: list[str], note: str = "") -> dict:
    return {
        "written": written,
        "say": say,
        "examples": [{"say": e, "result": apply_commands(e)} for e in examples],
        "note": note,
    }


def _punctuation() -> list[dict]:
    rows: dict[str, dict] = {}
    for command in COMMANDS:
        if command.spacing == BREAK:
            continue
        row = rows.setdefault(
            command.symbol,
            _row(command.symbol, [], _SYMBOL_EXAMPLES[command.symbol], _SYMBOL_NOTES.get(command.symbol, "")),
        )
        row["say"] += [p for p in command.phrases if p not in row["say"]]
    order = list(_SYMBOL_EXAMPLES)  # the order people learn them: . , : · ; ! …
    return sorted(rows.values(), key=lambda row: order.index(row["written"]))


def _breaks() -> list[dict]:
    names = {"\n\n": "Νέα παράγραφος", "\n": "Νέα γραμμή"}
    rows = [
        _row(names[c.symbol], list(c.phrases), [f"πρώτο άρθρο {c.phrases[0]} δεύτερο άρθρο"])
        for c in COMMANDS
        if c.spacing == BREAK
    ]
    rows.append(_row("Νέα παράγραφος", ["(παύση 2-3 δευτερολέπτων)"], [], "Μια μεγάλη παύση στην ομιλία ξεκινά επίσης νέα παράγραφο."))
    return rows


def _capitals() -> list[dict]:
    return [
        _row(
            "ΚΕΦΑΛΑΙΑ",
            [CAPS_ON_PHRASE, CAPS_OFF_PHRASE],
            [f"{CAPS_ON_PHRASE} συμβόλαιο αγοραπωλησίας {CAPS_OFF_PHRASE} στην Αθήνα σήμερα"],
            f"Ό,τι λέγεται ανάμεσα γράφεται με κεφαλαία, χωρίς τόνους. Χωρίς «{CAPS_OFF_PHRASE}» "
            "τα κεφαλαία σταματούν στο τέλος της ηχογράφησης. Το «κεφαλαία» μόνο του μένει λέξη.",
        )
    ]


def _numbering() -> list[dict]:
    first_names: dict[str, str] = {}
    for name, letter in LETTER_NAMES.items():
        first_names.setdefault(letter, name)
    return [
        _row(
            "1)  2)  3) …",
            ["αρίθμηση ένα", "αρίθμηση δύο", "αρίθμηση 3"],
            ["οι όροι είναι άνω κάτω τελεία αρίθμηση ένα το ακίνητο αρίθμηση δύο τα βάρη"],
            "Πάντα με τη λέξη «αρίθμηση»· κάθε σημείο ξεκινά σε νέα γραμμή. "
            "Χωρίς «αρίθμηση», το «δύο» γράφεται ως ποσό: δύο (2).",
        ),
        _row(
            "α)  β)  γ) …",
            ["άλφα παρένθεση", "αρίθμηση άλφα"],
            ["άλφα παρένθεση πρώτος όρος βήτα παρένθεση δεύτερος όρος"],
            "Τα γράμματα λέγονται με το όνομά τους: "
            + ", ".join(f"{name} = {letter}" for letter, name in first_names.items())
            + ". Εναλλακτικά: "
            + ", ".join(n for n in LETTER_NAMES if n != first_names[LETTER_NAMES[n]])
            + ".",
        ),
    ]


def _numbers() -> list[dict]:
    return [
        _row("είκοσι εννέα (29)", ["τον αριθμό όπως διαβάζεται"], ["εμβαδόν είκοσι εννέα"],
             "Οι αριθμοί γράφονται ολογράφως και αριθμητικά σε παρένθεση, με τις λέξεις όπως ειπώθηκαν."),
        _row("… ευρώ (250.000 €)", ["το ποσό και «ευρώ»"], ["αντί τιμήματος διακοσίων πενήντα χιλιάδων ευρώ"]),
        _row("… τοις εκατό (50%)", ["το ποσοστό και «τοις εκατό»"], ["ποσοστό πενήντα τοις εκατό εξ αδιαιρέτου"]),
        _row("… τετραγωνικών μέτρων (85 τ.μ.)", ["το εμβαδόν και «τετραγωνικά μέτρα»"],
             ["εμβαδού ογδόντα πέντε τετραγωνικών μέτρων"]),
        _row("(2)", ["άνοιγμα παρένθεσης", "κλείσιμο παρένθεσης"],
             ["τα δύο άνοιγμα παρένθεσης δύο κλείσιμο παρένθεσης μέρη"],
             "Όταν θέλετε μόνο τον αριθμό, χωρίς λέξεις."),
        _row("άρθρο 5", ["άρθρο / παράγραφος / αριθμός / νόμος / ΦΕΚ / ΑΦΜ / ΚΑΕΚ / οδός …"],
             ["σύμφωνα με το άρθρο πέντε του νόμου 4412 κάθετος 2016"],
             "Μετά από αυτές τις λέξεις ο αριθμός μένει μόνο με ψηφία. Το ίδιο για ημερομηνίες, "
             "ώρες, κωδικούς και αριθμούς με 5+ ψηφία."),
        _row("ένα ακίνητο", ["ένα / μία μόνο του"], ["ένα ακίνητο στην Αθήνα"],
             "Το «ένα» μόνο του θεωρείται άρθρο και δεν παίρνει αριθμό."),
    ]


def build_guide() -> list[dict]:
    return [
        {"title": "Σημεία στίξης και σύμβολα", "rows": _punctuation()},
        {"title": "Αλλαγή παραγράφου και γραμμής", "rows": _breaks()},
        {"title": "Κεφαλαία γράμματα", "rows": _capitals()},
        {"title": "Αρίθμηση", "rows": _numbering()},
        {"title": "Αριθμοί, ποσά, εμβαδά", "rows": _numbers()},
    ]
