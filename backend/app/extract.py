"""KYC document field extraction (passports, ID cards, company registration docs)."""

import json
import re

from .logging_config import logger
from .ocr import file_to_images, ocr_document, ocr_single_page

EXTRACTION_PROMPT = (
    "You are a KYC compliance assistant. Look at this identity or company document "
    "image and extract the key information as a single strict JSON object. Use these "
    "keys when the information is present in the document, and omit any key that does "
    "not apply: document_type, full_name, id_number, passport_number, date_of_birth, "
    "nationality, gender, address, company_name, registration_number, "
    "incorporation_date, issue_date, expiry_date, issuing_authority, place_of_birth. "
    "Respond with ONLY the JSON object - no explanation, no markdown code fences."
)


def _extract_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}

    snippet = raw[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r",\s*([}\]])", r"\1", snippet)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def extract_kyc(filename: str, file_bytes: bytes) -> dict:
    pages = file_to_images(filename, file_bytes)

    fields: dict = {}
    for i, page in enumerate(pages, start=1):
        raw = ocr_single_page(page, EXTRACTION_PROMPT, page_label=f"{filename} KYC page {i}/{len(pages)}")
        parsed = _extract_json(raw)
        if not parsed:
            logger.warning("Could not parse JSON fields from %s page %d; raw response: %s", filename, i, raw[:300])
        for key, value in parsed.items():
            if value in (None, "", "N/A", "n/a", "null"):
                continue
            fields.setdefault(key, value)

    ocr_result = ocr_document(filename, file_bytes)

    logger.info("KYC extraction for %s found %d field(s): %s", filename, len(fields), sorted(fields.keys()))

    return {
        "fields": fields,
        "raw_text": ocr_result["text"],
        "page_count": ocr_result["page_count"],
    }
