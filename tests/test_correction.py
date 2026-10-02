import dataclasses
import json

import pytest

from app import correction
from app.correction import apply_safe_changes, correct_text, sound


@pytest.mark.parametrize(
    "a, b",
    [("η", "οι"), ("γνωστή", "γνωστοί"), ("πωλείτε", "πωλείται"), ("της", "τις"), ("δήλωση", "δηλώσει"),
     ("ορίσο", "ορίσω"), ("τη", "την"), ("ή", "η"), ("γάμα", "γάμμα")],
)
def test_homophones_sound_the_same(a, b):
    assert sound(a) == sound(b)


@pytest.mark.parametrize("a, b", [("πωλητής", "αγοραστής"), ("το", "τον"), ("Γιώργος", "Γεώργιος")])
def test_different_words_sound_different(a, b):
    assert sound(a) != sound(b)


def test_only_homophone_changes_are_applied():
    text, changes = apply_safe_changes(
        "Η γνωστή πωλητές δηλώνουν ότι το ακίνητο πωλείτε ελεύθερο, εμβαδού (85 τ.μ.).",
        "Οι γνωστοί πωλητές δηλώνουν ρητά ότι το διαμέρισμα πωλείται ελεύθερο, εμβαδού (90 τ.μ.).",
    )
    # Added «ρητά», «ακίνητο» -> «διαμέρισμα» and 85 -> 90 are all rejected.
    assert text == "Οι γνωστοί πωλητές δηλώνουν ότι το ακίνητο πωλείται ελεύθερο, εμβαδού (85 τ.μ.)."
    assert [(c["from"], c["to"]) for c in changes] == [("Η", "Οι"), ("γνωστή", "γνωστοί"), ("πωλείτε", "πωλείται")]


def test_rewritten_text_is_ignored():
    assert apply_safe_changes("Ο πωλητής δηλώνει", "Κάτι εντελώς διαφορετικό εδώ") == ("Ο πωλητής δηλώνει", [])


def test_case_is_kept():
    assert apply_safe_changes("ΤΗΣ ΣΥΜΒΑΣΕΙΣ", "τις συμβάσεις")[0] == "ΤΙΣ ΣΥΜΒΑΣΕΙΣ"


def test_unreachable_server_returns_text_unchanged(monkeypatch):
    monkeypatch.setattr(correction, "settings", dataclasses.replace(correction.settings, ai_url="http://127.0.0.1:9"))
    result = correct_text("Η γνωστή πωλητές.")
    assert result["text"] == "Η γνωστή πωλητές."
    assert "παραλείφθηκε" in result["warning"]


def test_ollama_request_and_reply_cleanup(monkeypatch):
    sent = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            content = "<think>σκέψη</think>Έξοδος: «Οι γνωστοί πωλητές.»"
            return json.dumps({"message": {"content": content}}).encode()

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data)
        return Reply()

    monkeypatch.setattr(correction.urllib.request, "urlopen", fake_urlopen)
    assert correction.suggest("Η γνωστή πωλητές.") == "Οι γνωστοί πωλητές."
    assert sent["url"].endswith("/api/chat")
    assert sent["body"]["options"]["temperature"] == 0
    assert "ΜΟΝΟ" in sent["body"]["messages"][0]["content"]


def test_status_reports_flag_server_and_model(monkeypatch):
    off = dataclasses.replace(correction.settings, ai_correction=False)
    monkeypatch.setattr(correction, "settings", off)
    assert correction.status()["enabled"] is False

    down = dataclasses.replace(off, ai_correction=True, ai_url="http://127.0.0.1:9")
    monkeypatch.setattr(correction, "settings", down)
    info = correction.status()
    assert info["enabled"] and not info["reachable"] and "error" in info

    up = dataclasses.replace(down, ai_model="gemma3:12b")
    monkeypatch.setattr(correction, "settings", up)
    monkeypatch.setattr(correction, "_request", lambda path, payload=None, timeout=None: {"models": [{"name": "qwen3:8b"}]})
    info = correction.status()
    assert info["reachable"] and not info["installed"]
    assert "ollama pull gemma3:12b" in info["error"]
