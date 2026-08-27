import asyncio
import time

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .compare import compare_documents
from .extract import extract_kyc_async
from .logging_config import logger
from .ocr import Cancelled, OCRError, ocr_document_async

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/compare")
async def compare(
    request: Request,
    client_file: UploadFile = File(...),
    mizuho_file: UploadFile = File(...),
):
    client_bytes = await _read_upload(client_file)
    mizuho_bytes = await _read_upload(mizuho_file)
    logger.info(
        "Compare request: client=%s (%d bytes), mizuho=%s (%d bytes)",
        client_file.filename, len(client_bytes), mizuho_file.filename, len(mizuho_bytes),
    )

    async def is_cancelled() -> bool:
        return await request.is_disconnected()

    started = time.monotonic()
    try:
        client_result, mizuho_result = await asyncio.gather(
            ocr_document_async(client_file.filename, client_bytes, is_cancelled=is_cancelled),
            ocr_document_async(mizuho_file.filename, mizuho_bytes, is_cancelled=is_cancelled),
        )
    except Cancelled as exc:
        logger.info("Compare request stopped by client: %s", exc)
        raise HTTPException(400, "Stopped by client.") from None
    except OCRError as exc:
        logger.error("Compare request failed: %s", exc)
        raise HTTPException(502, str(exc)) from exc
    elapsed = time.monotonic() - started

    comparison = compare_documents(client_result["text"], mizuho_result["text"])
    total_pages = client_result["page_count"] + mizuho_result["page_count"]
    logger.info(
        "Compare request complete in %.1fs: match=%.1f%%, discrepancies=%d, pages=%d",
        elapsed, comparison["match_percentage"], len(comparison["discrepancies"]), total_pages,
    )

    return {
        "client_text": client_result["text"],
        "mizuho_text": mizuho_result["text"],
        **comparison,
        "timing": _timing(elapsed, total_pages),
    }


@app.post("/api/extract-kyc")
async def extract(request: Request, file: UploadFile = File(...)):
    file_bytes = await _read_upload(file)
    logger.info("KYC extraction request: %s (%d bytes)", file.filename, len(file_bytes))

    async def is_cancelled() -> bool:
        return await request.is_disconnected()

    started = time.monotonic()
    try:
        result = await extract_kyc_async(file.filename, file_bytes, is_cancelled=is_cancelled)
    except Cancelled as exc:
        logger.info("KYC extraction request stopped by client: %s", exc)
        raise HTTPException(400, "Stopped by client.") from None
    except OCRError as exc:
        logger.error("KYC extraction request failed: %s", exc)
        raise HTTPException(502, str(exc)) from exc
    elapsed = time.monotonic() - started

    result["timing"] = _timing(elapsed, result["page_count"])
    return result
