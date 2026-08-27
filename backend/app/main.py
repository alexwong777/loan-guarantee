import asyncio
import time

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .compare import compare_documents
from .extract import extract_kyc_async
from .guarantee_fields import extract_guarantee_fields_async
from .jobs import Job, TrackProgress, get_job, new_job, touch
from .logging_config import logger
from .ocr import Cancelled, OCRError, file_to_images, ocr_pages_async

app = FastAPI(title="Letter of Guarantee Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"}


async def _read_upload(file: UploadFile) -> bytes:
    suffix = ""
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1].lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {file.filename}")
    data = await file.read()
    if not data:
        raise HTTPException(400, f"{file.filename} is empty.")
    return data


def _timing(elapsed: float, total_pages: int) -> dict:
    return {
        "elapsed_seconds": round(elapsed, 1),
        "total_pages": total_pages,
        "avg_seconds_per_page": round(elapsed / total_pages, 1) if total_pages else None,
    }


def _serialize_tracks(job: Job) -> dict:
    return {
        name: {"label": t.label, "current": t.current, "total": t.total, "done": t.done}
        for name, t in job.tracks.items()
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def _run_compare_job(
    job: Job, client_filename: str, client_bytes: bytes, mizuho_filename: str, mizuho_bytes: bytes
):
    client_track = TrackProgress(label="Client")
    mizuho_track = TrackProgress(label="Mizuho")
    fields_track = TrackProgress(label="Key info")
    job.tracks = {"client": client_track, "mizuho": mizuho_track, "fields": fields_track}

    async def is_cancelled() -> bool:
        return job.cancel_requested

    async def safe_guarantee_fields(pages: list) -> dict:
        # Key Information is a bonus on top of the core comparison - a hiccup
        # extracting it (a bad response, a transient request failure) should
        # never fail the whole job. A user-initiated Stop should still
        # cancel it like everything else, so Cancelled is left to propagate.
        try:
            return await extract_guarantee_fields_async(
                pages, client_filename, is_cancelled=is_cancelled, track=fields_track
            )
        except Cancelled:
            raise
        except OCRError as exc:
            logger.warning("Key info extraction failed for %s: %s", client_filename, exc)
            fields_track.done = True
            return {}

    try:
        client_pages = file_to_images(client_filename, client_bytes)
        mizuho_pages = file_to_images(mizuho_filename, mizuho_bytes)

        client_result, mizuho_result, guarantee_fields = await asyncio.gather(
            ocr_pages_async(client_pages, client_filename, is_cancelled=is_cancelled, track=client_track),
            ocr_pages_async(mizuho_pages, mizuho_filename, is_cancelled=is_cancelled, track=mizuho_track),
            safe_guarantee_fields(client_pages),
        )
        comparison = compare_documents(client_result["text"], mizuho_result["text"])

        elapsed = time.monotonic() - job.started_at
        total_pages = client_result["page_count"] + mizuho_result["page_count"]
        job.result = {
            "client_text": client_result["text"],
            "mizuho_text": mizuho_result["text"],
            **comparison,
            "timing": _timing(elapsed, total_pages),
            "guarantee_fields": guarantee_fields,
        }
        job.status = "done"
        logger.info(
            "Compare job %s complete in %.1fs: match=%.1f%%, discrepancies=%d, pages=%d",
            job.id, elapsed, comparison["match_percentage"], len(comparison["discrepancies"]), total_pages,
        )
    except Cancelled as exc:
        job.status = "cancelled"
        logger.info("Compare job %s stopped: %s", job.id, exc)
    except OCRError as exc:
        job.status = "error"
        job.error = str(exc)
        logger.error("Compare job %s failed: %s", job.id, exc)
    except Exception as exc:  # noqa: BLE001 - keep the job's failure visible instead of hanging forever
        job.status = "error"
        job.error = str(exc)
        logger.exception("Compare job %s crashed unexpectedly", job.id)
    finally:
        touch(job)


@app.post("/api/compare/start")
async def compare_start(client_file: UploadFile = File(...), mizuho_file: UploadFile = File(...)):
    client_bytes = await _read_upload(client_file)
    mizuho_bytes = await _read_upload(mizuho_file)
    logger.info(
        "Compare request: client=%s (%d bytes), mizuho=%s (%d bytes)",
        client_file.filename, len(client_bytes), mizuho_file.filename, len(mizuho_bytes),
    )

    job = new_job("compare")
    asyncio.create_task(
        _run_compare_job(job, client_file.filename, client_bytes, mizuho_file.filename, mizuho_bytes)
    )
    return {"job_id": job.id}


async def _run_kyc_job(job: Job, filename: str, file_bytes: bytes):
    fields_track = TrackProgress(label="Fields")
    text_track = TrackProgress(label="Full text")
    job.tracks = {"fields": fields_track, "text": text_track}

    async def is_cancelled() -> bool:
        return job.cancel_requested

    try:
        result = await extract_kyc_async(
            filename, file_bytes, is_cancelled=is_cancelled, fields_track=fields_track, text_track=text_track
        )
        elapsed = time.monotonic() - job.started_at
        result["timing"] = _timing(elapsed, result["page_count"])
        job.result = result
        job.status = "done"
    except Cancelled as exc:
        job.status = "cancelled"
        logger.info("KYC job %s stopped: %s", job.id, exc)
    except OCRError as exc:
        job.status = "error"
        job.error = str(exc)
        logger.error("KYC job %s failed: %s", job.id, exc)
    except Exception as exc:  # noqa: BLE001 - keep the job's failure visible instead of hanging forever
        job.status = "error"
        job.error = str(exc)
        logger.exception("KYC job %s crashed unexpectedly", job.id)
    finally:
        touch(job)


@app.post("/api/extract-kyc/start")
async def extract_start(file: UploadFile = File(...)):
    file_bytes = await _read_upload(file)
    logger.info("KYC extraction request: %s (%d bytes)", file.filename, len(file_bytes))

    job = new_job("kyc")
    asyncio.create_task(_run_kyc_job(job, file.filename, file_bytes))
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found (it may have expired).")

    elapsed = time.monotonic() - job.started_at
    return {
        "status": job.status,
        "elapsed_seconds": round(elapsed, 1),
        "tracks": _serialize_tracks(job),
        "result": job.result,
        "error": job.error,
    }


@app.post("/api/jobs/{job_id}/stop")
async def job_stop(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found (it may have expired).")
    job.cancel_requested = True
    touch(job)
    return {"status": "stopping"}
