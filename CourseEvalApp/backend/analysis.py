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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException
from sqlalchemy import func, select

import config
import credits
from database import SessionLocal
from models import CreditMode, Report, Upload, User

logger = logging.getLogger("courseeval.analysis")

# Swappable in tests
session_factory = SessionLocal

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_runner = ThreadPoolExecutor(max_workers=1)


class AnalysisError(RuntimeError):
    pass


class JobLimitError(RuntimeError):
    """The user may not start another analysis right now (the message is shown to them)."""


ACTIVE_STATUSES = ("queued", "running")
MAX_ACTIVE_JOBS_PER_USER = 2      # queued or running analyses one person may have at once
MAX_ACTIVE_JOBS_TOTAL = 20        # whole queue; one shared worker runs them one at a time
MAX_COMMENTS_PER_ANALYSIS = 3000  # real evaluation files have a few hundred at most
FINISHED_JOB_TTL = timedelta(hours=24)  # finished jobs are forgotten after this (reports stay saved)


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


class StorageQuotaError(RuntimeError):
    """The person's stored files would pass their quota (the message is shown to them)."""


def safe_filename(name: str) -> str:
    """Shorten a file name to MAX_FILENAME_CHARS, keeping its extension (the database column holds 255)."""
    name = Path(name or "upload").name
    if len(name) <= config.MAX_FILENAME_CHARS:
        return name
    suffix = Path(name).suffix[:10]
    return name[: config.MAX_FILENAME_CHARS - len(suffix)] + suffix


def store_upload(db, user: User, original_name: str, content: bytes) -> Upload:
    used = db.scalar(select(func.coalesce(func.sum(Upload.size_bytes), 0)).where(Upload.owner_id == user.id)) or 0
    if used + len(content) > config.USER_STORAGE_QUOTA_MB * 1024 * 1024:
        raise StorageQuotaError(f"Your stored files would pass the {config.USER_STORAGE_QUOTA_MB} MB limit. "
                                "Delete some old reports to free space.")
    original_name = safe_filename(original_name)
    folder = config.STORAGE_DIR / "uploads" / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{Path(original_name).suffix.lower()}"
    stored.write_bytes(content)
    try:
        upload = Upload(owner_id=user.id, original_filename=original_name, stored_path=str(stored), size_bytes=len(content))
        db.add(upload)
        db.commit()
    except Exception:
        db.rollback()
        stored.unlink(missing_ok=True)  # do not leave a file with no database row
        raise
    return upload


def discard_upload(upload_id: int) -> None:
    """Delete a failed job's file and its upload row, unless a report still uses them."""
    try:
        with session_factory() as db:
            upload = db.get(Upload, upload_id)
            if upload is None or db.scalar(select(func.count()).select_from(Report).where(Report.upload_id == upload_id)):
                return
            Path(upload.stored_path).unlink(missing_ok=True)
            db.delete(upload)
            db.commit()
    except Exception:
        logger.exception("Could not remove the upload of a failed job (%s)", upload_id)


def _prune_finished_jobs(now: datetime) -> None:
    """Forget finished jobs older than FINISHED_JOB_TTL. Call with _jobs_lock held."""
    for job_id in [jid for jid, job in _jobs.items() if job["status"] not in ACTIVE_STATUSES
                   and now - datetime.fromisoformat(job["created"]) > FINISHED_JOB_TTL]:
        del _jobs[job_id]


def reserve(user: User, plan: credits.RunPlan, filename: str, course: str, term: str | None) -> str:
    """Register a queued job, refusing it when the user or the whole queue is over its in-flight limit.

    Checking and registering happen under one lock, so two uploads sent at the same moment cannot both pass.
    - Each person may have MAX_ACTIVE_JOBS_PER_USER analyses queued or running, so one account cannot fill
      the single shared worker; the whole queue holds at most MAX_ACTIVE_JOBS_TOTAL.
    - A capped professor may have one lab-credit analysis queued or running at a time: spend is only recorded
      when a job finishes, so more would let queued jobs run past the cap.
    """
    lab_credit = credits.uses_lab_credit(plan)
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _prune_finished_jobs(datetime.now(timezone.utc))
        active = [job for job in _jobs.values() if job["status"] in ACTIVE_STATUSES]
        mine = [job for job in active if job["owner_id"] == user.id]
        if len(active) >= MAX_ACTIVE_JOBS_TOTAL:
            raise JobLimitError("The analysis queue is full right now. Please try again in a few minutes.")
        if len(mine) >= MAX_ACTIVE_JOBS_PER_USER:
            raise JobLimitError(f"You already have {len(mine)} analyses waiting or running. "
                                "Please wait for one to finish before starting another.")
        if lab_credit and user.credit_mode == CreditMode.OUR_KEY_CAPPED and any(
            job["owner_id"] == user.id and job["lab_credit"] and job["status"] in ACTIVE_STATUSES for job in _jobs.values()
        ):
            raise JobLimitError("You already have an analysis running on lab AI credit. "
                                "Please wait for it to finish before starting another.")
        _jobs[job_id] = {
            "job_id": job_id,
            "owner_id": user.id,
            "filename": filename,
            "course": course,
            "term": term,
            "model_choice": plan.model_choice,
            "lab_credit": lab_credit,
            "status": "queued",
            "stage": None,
            "done": 0,
            "total": 0,
            "error": None,
            "report_id": None,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    return job_id


def release(job_id: str) -> None:
    """Drop a reserved job that never started (for example when storing the upload failed)."""
    with _jobs_lock:
        _jobs.pop(job_id, None)


def submit(job_id: str, user: User, upload: Upload, plan: credits.RunPlan, course: str, term: str | None) -> str:
    _runner.submit(_run, job_id, user.id, upload.id, plan, course, term)
    return job_id


def _run(job_id: str, user_id: int, upload_id: int, plan: credits.RunPlan, course: str, term: str | None) -> None:
    def progress(stage: str, done: int, total: int) -> None:
        _update(job_id, status="running", stage=stage, done=done, total=total)

    _update(job_id, status="running", stage="extracting")
    try:
        with session_factory() as db:
            if credits.uses_lab_credit(plan):
                # Spend is recorded only when a job finishes, so re-check the cap and lab budget before spending
                try:
                    credits.check_lab_credit(db, db.get(User, user_id))
                except HTTPException as exc:
                    raise AnalysisError(exc.detail) from exc
            upload = db.get(Upload, upload_id)
            data = extract_comments(Path(upload.stored_path), upload.original_filename)
            if not data.get("responses"):
                warnings = "; ".join(data.get("warnings", [])) or "No written student comments were found in this file."
                raise AnalysisError(warnings)
            if len(data["responses"]) > MAX_COMMENTS_PER_ANALYSIS:
                raise AnalysisError(f"This file has {len(data['responses'])} comments, more than the {MAX_COMMENTS_PER_ANALYSIS} "
                                    "one analysis can take. Please split it into smaller files.")

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
        discard_upload(upload_id)
    except requests.RequestException as exc:
        logger.exception("OCR server problem in job %s", job_id)
        _update(job_id, status="failed", error=f"The text-extraction server could not be reached ({exc.__class__.__name__}).")
        discard_upload(upload_id)
    except Exception:
        logger.exception("Job %s failed", job_id)
        _update(job_id, status="failed", error="The analysis failed unexpectedly. Please try again or contact the administrator.")
        discard_upload(upload_id)
    finally:
        plan.api_key = None  # drop the decrypted own key from memory
