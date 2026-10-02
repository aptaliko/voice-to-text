import logging
import secrets
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ocr, transcribe
from .config import settings
from .docx_export import build_docx
from .jobs import JobQueue

log = logging.getLogger("voice-to-text")
STATIC_DIR = Path(__file__).parent / "static"
AUDIO_EXTENSIONS = {".webm", ".ogg", ".oga", ".opus", ".mp3", ".m4a", ".mp4", ".wav", ".flac", ".aac", ".amr", ".3gp"}

security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    if not settings.username:
        return  # auth disabled (local development only)
    valid = credentials is not None and (
        secrets.compare_digest(credentials.username.encode(), settings.username.encode())
        & secrets.compare_digest(credentials.password.encode(), settings.password.encode())
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="voice-to-text", charset="UTF-8"'},
        )


app = FastAPI(title="Voice to text", docs_url=None, redoc_url=None, openapi_url=None)
jobs = JobQueue(ttl_seconds=settings.job_ttl_seconds)

if not settings.username:
    log.warning("APP_USERNAME is not set: authentication is DISABLED")


async def _save_upload(upload: UploadFile, allowed: set[str]) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Μη υποστηριζόμενος τύπος αρχείου: {suffix or '-'}")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with path.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    f"Το αρχείο ξεπερνά τα {settings.max_upload_mb} MB",
                )
            out.write(chunk)
    return path


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/transcribe", dependencies=[Depends(require_auth)])
async def submit_transcription(file: UploadFile) -> dict:
    path = await _save_upload(file, AUDIO_EXTENSIONS)
    return jobs.submit("audio", file.filename or "", path, transcribe.transcribe).public()


@app.post("/api/ocr", dependencies=[Depends(require_auth)])
async def submit_ocr(file: UploadFile) -> dict:
    path = await _save_upload(file, ocr.IMAGE_EXTENSIONS | ocr.PDF_EXTENSIONS)
    return jobs.submit("ocr", file.filename or "", path, ocr.extract_text).public()


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_auth)])
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Η εργασία δεν βρέθηκε")
    return job.public()


class ExportRequest(BaseModel):
    text: str
    title: str = ""
    filename: str = "symvolaio"


@app.post("/api/export", dependencies=[Depends(require_auth)])
def export_docx(request: ExportRequest) -> Response:
    name = (request.filename.strip() or "symvolaio").removesuffix(".docx") + ".docx"
    return Response(
        content=build_docx(request.text, request.title),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=\"document.docx\"; filename*=UTF-8''{quote(name)}"},
    )


@app.get("/", dependencies=[Depends(require_auth)])
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
