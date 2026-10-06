"""The dictionary in the page must cover every dictation rule."""

from app.dictation import CAPS_OFF_PHRASE, CAPS_ON_PHRASE, COMMANDS, LETTER_NAMES
from app.guide import build_guide


def _all_text() -> str:
    parts = []
    for section in build_guide():
        for row in section["rows"]:
            parts += [row["written"], row["note"], *row["say"]]
            parts += [e["say"] for e in row["examples"]]
    return " ".join(parts)


def test_every_voice_command_is_in_the_dictionary():
    text = _all_text()
    phrases = [p for c in COMMANDS for p in c.phrases] + [CAPS_ON_PHRASE, CAPS_OFF_PHRASE, "αρίθμηση"]
    missing = [p for p in phrases if p not in text]
    assert not missing, f"Add these to app/guide.py: {missing}"


def test_every_list_letter_is_in_the_dictionary():
    text = _all_text()
    assert not [name for name in LETTER_NAMES if name not in text]


def test_symbol_examples_really_produce_the_symbol():
    punctuation = build_guide()[0]["rows"]
    assert {row["written"] for row in punctuation} == {c.symbol for c in COMMANDS if c.symbol.strip()}
    for row in punctuation:
        assert row["examples"], row["written"]
        assert all(row["written"] in e["result"] for e in row["examples"]), row


def test_guide_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    response = TestClient(main.app).get("/api/guide", auth=("user", "secret"))
    assert response.status_code == 200
    first = response.json()[0]["rows"][0]
    assert first["written"] == "." and first["examples"][0]["result"].endswith("Ο αγοραστής αποδέχεται")
