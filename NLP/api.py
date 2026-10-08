from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import uvicorn
import logging
import re
import shutil
import threading
import time
import os
import json
import uuid
import requests
import zipfile
from io import BytesIO
from datetime import datetime
from pathlib import Path

from main import analysis_pipeline
import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nlp_api")


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """When NLP_API_KEY is set, every request must send it in the X-API-Key header."""
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Missing or wrong API key")


app = FastAPI(title="Course Evaluation NLP API", dependencies=[Depends(verify_api_key)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# 📂 Define local directory paths
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "saved_inputs"
RESULT_DIR = BASE_DIR / "saved_results"
HISTORY_FILE = BASE_DIR / "history.json"

# Ensure directories exist
INPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_CHOICES = {"local", "openai", "anthropic"}
SAFE_COURSE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()&,'-]*")

_history_lock = threading.Lock()


class ProcessingError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# --- File names and paths ---------------------------------------------------------
def safe_filename(filename: str | None) -> str:
    """Keep only the base name and harmless characters, so uploads can't escape saved_inputs/."""
    name = Path(str(filename or "")).name
    name = re.sub(r"[^A-Za-z0-9 ._()&,'-]", "_", name).strip(" .")
    return name or "upload"


def checked_course_id(course_id: str) -> str:
    if not SAFE_COURSE_ID.fullmatch(course_id or "") or ".." in course_id:
        raise HTTPException(status_code=400, detail="Invalid course ID")
    return course_id


def result_json_path(course_id: str) -> Path:
    path = (RESULT_DIR / f"{checked_course_id(course_id)}_COMBINED_REPORT.json").resolve()
    if path.parent != RESULT_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid course ID")
    return path


def archive_previous_result(course_id: str) -> None:
    """Re-uploading the same file used to overwrite the old report silently; keep it in archive/ instead."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = RESULT_DIR / "archive"
    for suffix in (".json", ".csv"):
        old = RESULT_DIR / f"{course_id}_COMBINED_REPORT{suffix}"
        if old.exists():
            archive_dir.mkdir(exist_ok=True)
            shutil.move(str(old), str(archive_dir / f"{course_id}_{stamp}_COMBINED_REPORT{suffix}"))


# --- Run history (history.json) ---------------------------------------------------
def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history_data):
    # Write to a temp file first, then swap it in, so a crash never leaves a half-written history
    temp_path = HISTORY_FILE.with_suffix(".json.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2)
    os.replace(temp_path, HISTORY_FILE)


def append_history(entry: dict) -> None:
    with _history_lock:
        history = load_history()
        history.append(entry)
        save_history(history)


# --- Processing -------------------------------------------------------------------
def process_upload(filename: str, content: bytes, model_choice: str, progress=None) -> dict:
    """Save the upload, extract comments with the OCR server, run the pipeline and record history."""
    start_time = time.time()
    course_id = Path(filename).stem
    current_date = datetime.now().strftime("%m-%d-%Y")

    def record(status: str) -> None:
        append_history({
            "filename": filename,
            "course_id": course_id,
            "date": current_date,
            "runtime_seconds": round(time.time() - start_time, 2),
            "status": status,
        })

    # 1. Save raw file permanently to local storage
    saved_file_path = INPUT_DIR / filename
    try:
        saved_file_path.write_bytes(content)
    except Exception as e:
        record(f"Save Failed: {e}")
        raise ProcessingError(500, f"Failed to save uploaded file: {e}")

    # 2. Extract comments with the OCR server
    if progress:
        progress("extracting", 0, 0)
    try:
        with open(saved_file_path, "rb") as f:
            ocr_response = requests.post(settings.OCR_URL, files={"file": (filename, f)}, timeout=300)
        ocr_response.raise_for_status()
        ocr_data = ocr_response.json()
    except Exception as e:
        record(f"OCR Failed: {e}")
        raise ProcessingError(502, f"OCR Server communication failed: {e}")

    # 3. Use whole responses (with their survey question) when the OCR server provides them
    if isinstance(ocr_data.get("responses"), list):
        raw_comments = ocr_data["responses"]
    else:
        extracted_text = ocr_data.get("extracted_text", "")
        raw_comments = [line.strip() for line in extracted_text.split('\n') if len(line.strip()) > 10]

    if not raw_comments:
        warnings = "; ".join(ocr_data.get("warnings", [])) or "No written student comments were found."
        record(f"No comments: {warnings}")
        raise ProcessingError(422, warnings)

    # 4. Run the pipeline and save the results permanently
    try:
        archive_previous_result(course_id)
        analysis_data = analysis_pipeline(
            course_id=course_id,
            raw_comments=raw_comments,
            output_dir=RESULT_DIR,
            write_files=True,
            model_choice=model_choice,
            quantitative=ocr_data.get("quantitative", []),
            extraction={"parser": ocr_data.get("parser", ""), "warnings": ocr_data.get("warnings", [])},
            progress=progress,
        )
    except Exception as e:
        logger.exception("Pipeline failed for %s", filename)
        record(f"Pipeline Failed: {e}")
        raise ProcessingError(500, f"Analysis pipeline failed: {e}")

    runtime = round(time.time() - start_time, 2)
    record("Success")
    return {"status": "success", "time_taken": runtime, "data": analysis_data}


def read_upload(file: UploadFile, model_choice: str) -> tuple[str, bytes]:
    if model_choice not in MODEL_CHOICES:
        raise HTTPException(status_code=400, detail=f"model_choice must be one of {sorted(MODEL_CHOICES)}")
    return safe_filename(file.filename), file.file.read()


# Plain `def` endpoints run in FastAPI's thread pool, so a long analysis no longer freezes /api/history
@app.post("/api/analyze")
def analyze_document(file: UploadFile = File(...), model_choice: str = Form("local")):
    """Process one file and wait for the finished report (used by the admin dashboard)."""
    filename, content = read_upload(file, model_choice)
    try:
        return process_upload(filename, content, model_choice)
    except ProcessingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# --- Background jobs: submit a file, then poll for progress -------------------------
JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()
# One file at a time; the pipeline already runs its LLM calls in parallel
_job_runner = ThreadPoolExecutor(max_workers=1)


def _update_job(job_id: str, **fields) -> None:
    with _jobs_lock:
        JOBS[job_id].update(fields)


def _run_job(job_id: str, filename: str, content: bytes, model_choice: str) -> None:
    def progress(stage: str, done: int, total: int) -> None:
        _update_job(job_id, status="running", stage=stage, done=done, total=total)

    _update_job(job_id, status="running", started=datetime.now().isoformat(timespec="seconds"))
    try:
        result = process_upload(filename, content, model_choice, progress=progress)
        _update_job(job_id, status="complete", runtime_seconds=result["time_taken"],
                    overall_score=result["data"].get("overall_score"))
    except ProcessingError as e:
        _update_job(job_id, status="failed", error=e.detail, error_code=e.status_code)
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        _update_job(job_id, status="failed", error=str(e), error_code=500)
    finally:
        _update_job(job_id, finished=datetime.now().isoformat(timespec="seconds"))


@app.post("/api/jobs")
def create_job(file: UploadFile = File(...), model_choice: str = Form("local")):
    """Queue a file and return immediately with a job ID; poll GET /api/jobs/{job_id} for progress."""
    filename, content = read_upload(file, model_choice)
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        JOBS[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "course_id": Path(filename).stem,
            "model_choice": model_choice,
            "status": "queued",
            "stage": None,
            "done": 0,
            "total": 0,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
    _job_runner.submit(_run_job, job_id, filename, content, model_choice)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs")
def list_jobs():
    with _jobs_lock:
        return sorted(JOBS.values(), key=lambda job: job["created"], reverse=True)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with _jobs_lock:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(job)


# --- History and downloads ----------------------------------------------------------
@app.get("/api/history")
def get_history():
    return load_history()


class ZipDownloadRequest(BaseModel):
    course_ids: list[str]


@app.post("/api/download-zip")
def download_zip(req: ZipDownloadRequest):
    if not req.course_ids:
        raise HTTPException(status_code=400, detail="No course IDs selected")

    # Build the ZIP in memory and stream it back (no shared temp file on disk)
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        files_added = 0
        for cid in req.course_ids:
            json_file = result_json_path(cid)
            if json_file.exists():
                zip_file.write(json_file, arcname=f"{cid}_Evaluation_Data.json")
                files_added += 1
    if files_added == 0:
        raise HTTPException(status_code=404, detail="No matching result files found to package")

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": 'attachment; filename="course_evaluations_export.zip"'},
    )


@app.get("/api/download/{course_id}")
def download_single(course_id: str):
    json_file = result_json_path(course_id)
    if not json_file.exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(
        path=json_file,
        media_type="application/json",
        filename=f"{course_id}_Evaluation_Data.json"
    )


@app.delete("/api/history")
def clear_history():
    with _history_lock:
        save_history([])
    return {"status": "success", "message": "History cleared"}


if __name__ == "__main__":
    logger.info("Starting NLP API on http://%s:%s", settings.API_HOST, settings.API_PORT)
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
