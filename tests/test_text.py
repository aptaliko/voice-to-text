from app.ocr import fix_homoglyphs, reflow
from app.dictation import apply_commands
from app.transcribe import join_segments


def test_long_pause_starts_new_paragraph():
    segments = [(0.0, 2.0, " Ο πωλητής"), (2.1, 4.0, " πωλεί το ακίνητο."), (8.0, 10.0, " Το τίμημα ορίζεται.")]
    assert join_segments(segments) == "Ο πωλητής πωλεί το ακίνητο.\n\nΤο τίμημα ορίζεται."


def test_spoken_commands():
    text = "Πρώτο άρθρο. Νέα παράγραφος. δεύτερο άρθρο, νέα γραμμή τρίτη γραμμή"
    assert apply_commands(text) == "Πρώτο άρθρο.\n\nΔεύτερο άρθρο\nΤρίτη γραμμή"


def test_spoken_commands_without_accents():
    assert apply_commands("πρώτο νεα παραγραφος δεύτερο") == "πρώτο\n\nΔεύτερο"


def test_reflow_joins_lines_and_hyphenation():
    raw = "Στην Αθήνα σήμερα\nυπογράφεται το συμ-\nβόλαιο.\n\nΆρθρο 2\n"
    assert reflow(raw) == "Στην Αθήνα σήμερα υπογράφεται το συμβόλαιο.\n\nΆρθρο 2"


def test_fix_homoglyphs_only_in_greek_words():
    assert fix_homoglyphs("σήµερα ΣYMBOΛAIO Athens 50 m2") == "σήμερα ΣΥΜΒΟΛΑΙΟ Athens 50 m2"


def test_reflow_keeps_numbered_items_on_their_own_line():
    raw = "Δηλώνει ότι:\n1) το ακίνητο είναι\nελεύθερο,\n2. χωρίς βάρη\nα) πρώτο\nτο ποσό των\n1.000 ευρώ και ο\nκ. Παπαδόπουλος"
    assert reflow(raw) == (
        "Δηλώνει ότι:\n1) το ακίνητο είναι ελεύθερο,\n2. χωρίς βάρη\nα) πρώτο το ποσό των 1.000 ευρώ και ο κ. Παπαδόπουλος"
    )
