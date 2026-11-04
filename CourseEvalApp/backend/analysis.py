"""Running an analysis for a signed-in user: store the upload, extract comments, run the NLP pipeline,
save the report and record what it cost.

Jobs run one at a time in a background thread (the pipeline itself makes its AI calls in parallel).
Job progress lives in memory; finished reports are in the database.
"""
from __future__ import annotations

import importlib
import logging
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import config
import credits
from database import SessionLocal
from models import Report, Upload, User

logger = logging.getLogger("courseeval.analysis")

# Swappable in tests
session_factory = SessionLocal

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_runner = ThreadPoolExecutor(max_workers=1)


class AnalysisError(RuntimeError):
    pass


# --- NLP pipeline and OCR ---------------------------------------------------------
_pipeline = None


def load_pipeline():
    """Import NLP/main.py once. It brings its own settings (NLP/.env holds the lab OpenAI key)."""
    global _pipeline
    if _pipeline is None:
        nlp_dir = str(config.NLP_DIR)
        if nlp_dir not in sys.path:
            sys.path.insert(0, nlp_dir)
        _pipeline = importlib.import_module("main")
    return _pipeline


def extract_comments(path: Path, original_name: str) -> dict[str, Any]:
    with open(path, "rb") as handle:
        response = requests.post(config.OCR_URL, files={"file": (original_name, handle)}, timeout=300)
    if response.status_code == 400:
        raise AnalysisError(response.json().get("detail", "This file type can't be read."))
    response.raise_for_status()
    return response.json()


def run_pipeline(course_id: str, data: dict[str, Any], plan: credits.RunPlan, progress) -> dict[str, Any]:
    nlp = load_pipeline()
    try:
        return nlp.analysis_pipeline(
            course_id=course_id,
            raw_comments=data.get("responses") or [],
            write_files=False,
            model_choice=plan.model_choice,
            quantitative=data.get("quantitative", []),
            extraction={"parser": data.get("parser", ""), "warnings": data.get("warnings", [])},
            progress=progress,
            api_key=plan.api_key,
            model_id=plan.model_id,
        )
    except Exception as exc:
        if type(exc).__name__ == "LLMAccountError":
            raise AnalysisError(str(exc)) from exc
        raise


# --- Jobs -------------------------------------------------------------------------
def _update(job_id: str, **fields) -> None:
    with _jobs_lock:
        _jobs[job_id].update(fields)


def get_job(job_id: str, owner_id: int) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job and job["owner_id"] == owner_id else None


def list_jobs(owner_id: int) -> list[dict[str, Any]]:
    with _jobs_lock:
        jobs = [dict(j) for j in _jobs.values() if j["owner_id"] == owner_id]
    return sorted(jobs, key=lambda j: j["created"], reverse=True)


def store_upload(db, user: User, original_name: str, content: bytes) -> Upload:
    folder = config.STORAGE_DIR / "uploads" / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{Path(original_name).suffix.lower()}"
    stored.write_bytes(content)
    upload = Upload(owner_id=user.id, original_filename=original_name, stored_path=str(stored), size_bytes=len(content))
    db.add(upload)
    db.commit()
    return upload


def submit(user: User, upload: Upload, plan: credits.RunPlan, course: str, term: str | None) -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "owner_id": user.id,
            "filename": upload.original_filename,
            "course": course,
            "term": term,
            "model_choice": plan.model_choice,
            "status": "queued",
            "stage": None,
            "done": 0,
            "total": 0,
            "error": None,
            "report_id": None,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    _runner.submit(_run, job_id, user.id, upload.id, plan, course, term)
    return job_id


def _run(job_id: str, user_id: int, upload_id: int, plan: credits.RunPlan, course: str, term: str | None) -> None:
    def progress(stage: str, done: int, total: int) -> None:
        _update(job_id, status="running", stage=stage, done=done, total=total)

    _update(job_id, status="running", stage="extracting")
    try:
        with session_factory() as db:
            upload = db.get(Upload, upload_id)
            data = extract_comments(Path(upload.stored_path), upload.original_filename)
            if not data.get("responses"):
                warnings = "; ".join(data.get("warnings", [])) or "No written student comments were found in this file."
                raise AnalysisError(warnings)

            report_data = run_pipeline(course, data, plan, progress)

            user = db.get(User, user_id)
            report = Report(
                owner_id=user_id,
                upload_id=upload_id,
                course=course,
                term=term,
                model=report_data.get("metadata", {}).get("model_id") or plan.model_choice,
                overall_score=report_data.get("overall_score"),
                report_json=report_data,
            )
            db.add(report)
            db.commit()
            credits.record_usage(db, user, report_data.get("metadata", {}).get("usage", {}), plan, report_id=report.id)
            _update(job_id, status="complete", stage="done", report_id=report.id)
            logger.info("Job %s finished: report %s for user %s", job_id, report.id, user_id)
    except AnalysisError as exc:
        _update(job_id, status="failed", error=str(exc))
    except requests.RequestException as exc:
        logger.exception("OCR server problem in job %s", job_id)
        _update(job_id, status="failed", error=f"The text-extraction server could not be reached ({exc.__class__.__name__}).")
    except Exception:
        logger.exception("Job %s failed", job_id)
        _update(job_id, status="failed", error="The analysis failed unexpectedly. Please try again or contact the administrator.")
    finally:
        plan.api_key = None  # drop the decrypted own key from memory
