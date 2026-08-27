"""KYC document field extraction (passports, ID cards, company registration docs,
address-proof documents, etc). The model is asked to identify what kind of document
it's looking at and pull out whatever relevant fields are actually printed on it -
the caller never has to say up front what type of document was uploaded.
"""

import asyncio
import json
import re
from typing import Optional

from .jobs import TrackProgress
from .logging_config import logger
from .ocr import Cancelled, IsCancelled, file_to_images, ocr_pages_async, ocr_single_page

EXTRACTION_PROMPT = (
    "You are a KYC compliance assistant. First identify what kind of document this image "
    "is (passport, national ID, company registration certificate, address proof such as a "
    "utility bill or bank statement, etc.), then extract whatever key identity, company, or "
    "financial information is actually printed on it. Use these keys when the information is "
    "present, and omit any key that does not apply: document_type, full_name, id_number, "
    "passport_number, date_of_birth, nationality, gender, address, company_name, "
    "registration_number, incorporation_date, issue_date, expiry_date, issuing_authority, "
    "place_of_birth, phone_number, email, bank_name, account_number. "
    "Respond with ONLY a single valid JSON object - no markdown code fences, no comments, no "
    "trailing commas. Every key and every string value must be wrapped in double quotes. Keep "
    "the JSON compact."
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_UNQUOTED_KEY_RE = re.compile(r'([{,]\s*)"?([A-Za-z_][A-Za-z0-9_]*)"?\s*:')
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_KV_FALLBACK_RE = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _strip_fence(raw: str) -> str:
    match = _FENCE_RE.search(raw)
    return match.group(1) if match else raw


def _normalize_keys(snippet: str) -> str:
    """Quotes bare keys (`name:`) and fixes keys missing their opening quote
    (`name":`), which is the malformed shape GLM-OCR sometimes produces."""
    return _UNQUOTED_KEY_RE.sub(r'\1"\2":', snippet)


def _balance(snippet: str) -> str:
    """Best-effort repair for output that got cut off mid-string/object."""
    if snippet.count('"') % 2 == 1:
        snippet += '"'
    snippet += "}" * max(0, snippet.count("{") - snippet.count("}"))
    snippet += "]" * max(0, snippet.count("[") - snippet.count("]"))
    return snippet


def _extract_json(raw: str) -> dict:
    text = _strip_fence(raw)
    start, end = text.find("{"), text.rfind("}")
    snippet = text[start : end + 1] if start != -1 and end != -1 and end > start else text

    for candidate in (snippet, _normalize_keys(snippet)):
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", candidate)
        for attempt in (cleaned, _balance(cleaned)):
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                continue

    # Last resort: pull out whichever "key": "value" pairs are well-formed on
    # their own, even if the JSON around them is broken or truncated.
    return {m.group(1): m.group(2) for m in _KV_FALLBACK_RE.finditer(_normalize_keys(snippet))}


async def extract_kyc_async(
    filename: str,
    file_bytes: bytes,
    is_cancelled: IsCancelled = None,
    fields_track: Optional[TrackProgress] = None,
    text_track: Optional[TrackProgress] = None,
) -> dict:
    pages = file_to_images(filename, file_bytes)
    total = len(pages)
    if fields_track is not None:
        fields_track.total = total

    async def extract_fields() -> dict:
        fields: dict = {}
        for i, page in enumerate(pages, start=1):
            if is_cancelled is not None and await is_cancelled():
                logger.info("Stopping KYC extraction for %s before page %d/%d (cancelled).", filename, i, total)
                raise Cancelled(f"Stopped before page {i}/{total}.")

            if fields_track is not None:
                fields_track.current = i

            raw = await asyncio.to_thread(
                ocr_single_page, page, EXTRACTION_PROMPT, page_label=f"{filename} KYC page {i}/{total}"
            )
            parsed = _extract_json(raw)
            if not parsed:
                logger.warning("Could not parse any fields from %s page %d; raw response: %s", filename, i, raw[:500])
            for key, value in parsed.items():
                if value in (None, "", "N/A", "n/a", "null"):
                    continue
                fields.setdefault(key, value)

        if fields_track is not None:
            fields_track.done = True
        return fields

    fields, ocr_result = await asyncio.gather(
        extract_fields(),
        ocr_pages_async(pages, filename, is_cancelled=is_cancelled, track=text_track),
    )

    logger.info("KYC extraction for %s found %d field(s): %s", filename, len(fields), sorted(fields.keys()))

    return {
        "fields": fields,
        "raw_text": ocr_result["text"],
        "page_count": ocr_result["page_count"],
    }
