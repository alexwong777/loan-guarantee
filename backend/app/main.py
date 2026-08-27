from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .compare import compare_documents
from .extract import extract_kyc
from .logging_config import logger
from .ocr import OCRError, ocr_document

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/compare")
async def compare(
    client_file: UploadFile = File(...),
    mizuho_file: UploadFile = File(...),
):
    client_bytes = await _read_upload(client_file)
    mizuho_bytes = await _read_upload(mizuho_file)
    logger.info(
        "Compare request: client=%s (%d bytes), mizuho=%s (%d bytes)",
        client_file.filename, len(client_bytes), mizuho_file.filename, len(mizuho_bytes),
    )

    try:
        client_result = ocr_document(client_file.filename, client_bytes)
        mizuho_result = ocr_document(mizuho_file.filename, mizuho_bytes)
    except OCRError as exc:
        logger.error("Compare request failed: %s", exc)
        raise HTTPException(502, str(exc)) from exc

    comparison = compare_documents(client_result["text"], mizuho_result["text"])
    logger.info("Compare request complete: match=%.1f%%, discrepancies=%d",
                comparison["match_percentage"], len(comparison["discrepancies"]))

    return {
        "client_text": client_result["text"],
        "mizuho_text": mizuho_result["text"],
        **comparison,
    }


@app.post("/api/extract-kyc")
async def extract(file: UploadFile = File(...)):
    file_bytes = await _read_upload(file)
    logger.info("KYC extraction request: %s (%d bytes)", file.filename, len(file_bytes))

    try:
        result = extract_kyc(file.filename, file_bytes)
    except OCRError as exc:
        logger.error("KYC extraction request failed: %s", exc)
        raise HTTPException(502, str(exc)) from exc

    return result
