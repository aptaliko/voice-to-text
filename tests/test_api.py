import dataclasses
import time

import pytest
from fastapi.testclient import TestClient

from app import main

AUTH = ("user", "secret")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.transcribe, "transcribe", lambda path, progress, correct=False: f"κείμενο από {path.suffix}")
    return TestClient(main.app)


def wait_for(client, job_id):
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}", auth=AUTH).json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_requires_auth(client):
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("user", "wrong")).status_code == 401
    assert client.get("/", auth=AUTH).status_code == 200
    assert client.get("/api/health").status_code == 200


def test_transcription_job_flow_and_upload_cleanup(client):
    response = client.post("/api/transcribe", auth=AUTH, files={"file": ("rec.webm", b"audio", "audio/webm")})
    assert response.status_code == 200
    job = wait_for(client, response.json()["id"])
    assert job["status"] == "done"
    assert job["text"] == "κείμενο από .webm"
    assert not any(main.settings.upload_dir.iterdir())


def test_rejects_unknown_type_and_oversized_files(client):
    assert client.post("/api/transcribe", auth=AUTH, files={"file": ("x.exe", b"x")}).status_code == 400
    big = b"0" * (2 * 1024 * 1024)
    assert client.post("/api/ocr", auth=AUTH, files={"file": ("scan.png", big)}).status_code == 413


def test_processing_error_is_reported(client):
    response = client.post("/api/ocr", auth=AUTH, files={"file": ("broken.png", b"not an image")})
    job = wait_for(client, response.json()["id"])
    assert job["status"] == "error"
    assert job["error"]


def test_export_docx(client):
    response = client.post("/api/export", auth=AUTH, json={"text": "Άρθρο 1", "filename": "Συμβόλαιο Παπαδόπουλος"})
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
    assert "filename*=UTF-8''%CE%A3" in response.headers["content-disposition"]


def test_ai_is_off_by_default(client):
    assert client.get("/api/config", auth=AUTH).json()["ai"]["enabled"] is False
    assert client.post("/api/correct", auth=AUTH, json={"text": "κείμενο"}).status_code == 400
    response = client.post("/api/transcribe", auth=AUTH, data={"correct": "true"}, files={"file": ("r.webm", b"a")})
    assert response.status_code == 400


def test_ai_correction_job(client, monkeypatch):
    enabled = dataclasses.replace(main.settings, ai_correction=True)
    monkeypatch.setattr(main, "settings", enabled)
    monkeypatch.setattr(main.correction, "settings", enabled)
    monkeypatch.setattr(main.correction, "suggest", lambda text: text.replace("Η γνωστή", "Οι γνωστοί"))
    response = client.post("/api/correct", auth=AUTH, json={"text": "Η γνωστή πωλητές.\n\nΆρθρο 2"})
    job = wait_for(client, response.json()["id"])
    assert job["status"] == "done"
    assert job["text"] == "Οι γνωστοί πωλητές.\n\nΆρθρο 2"
    assert job["original"] == "Η γνωστή πωλητές.\n\nΆρθρο 2"
    assert [(c["from"], c["to"]) for c in job["corrections"]] == [("Η", "Οι"), ("γνωστή", "γνωστοί")]
