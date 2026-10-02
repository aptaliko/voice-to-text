"""In-memory job queue.

Transcription and OCR are CPU heavy, so jobs run one at a time on a single
worker thread. That keeps the server responsive for the website it shares
the machine with. Results live in memory only and expire after a TTL.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ProgressFn = Callable[[float], None]
# A processor returns the text, or a dict with "text" and optionally
# "original", "corrections" and "warning" (AI correction results).
Processor = Callable[[Path | None, ProgressFn], "str | dict"]


@dataclass
class Job:
    id: str
    kind: str
    filename: str
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    text: str = ""
    error: str = ""
    original: str = ""  # text before AI correction
    corrections: list = field(default_factory=list)
    warning: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "filename": self.filename,
            "status": self.status,
            "progress": round(self.progress, 3),
            "text": self.text,
            "error": self.error,
            "original": self.original,
            "corrections": self.corrections,
            "warning": self.warning,
        }


class JobQueue:
    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")

    def submit(self, kind: str, filename: str, path: Path | None, processor: Processor) -> Job:
        self._expire()
        job = Job(id=uuid.uuid4().hex, kind=kind, filename=filename)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job, path, processor)
        return job

    def get(self, job_id: str) -> Job | None:
        self._expire()
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job: Job, path: Path, processor: Processor) -> None:
        job.status = "running"

        def report(progress: float) -> None:
            job.progress = min(max(progress, 0.0), 1.0)

        try:
            result = processor(path, report)
            if isinstance(result, dict):
                job.text = result["text"]
                job.original = result.get("original", "")
                job.corrections = result.get("corrections", [])
                job.warning = result.get("warning", "")
            else:
                job.text = result
            job.progress = 1.0
            job.status = "done"
        except Exception as exc:  # surfaced to the user in the UI
            job.error = str(exc) or exc.__class__.__name__
            job.status = "error"
        finally:
            job.finished_at = time.time()
            if path is not None:
                path.unlink(missing_ok=True)

    def _expire(self) -> None:
        cutoff = time.time() - self._ttl
        with self._lock:
            for job_id in [j.id for j in self._jobs.values() if j.finished_at and j.finished_at < cutoff]:
                del self._jobs[job_id]
