"""KYC document field extraction (passports, ID cards, company registration docs,
address-proof documents, etc). The model is asked to identify what kind of document
it's looking at and pull out whatever relevant fields are actually printed on it -
the caller never has to say up front what type of document was uploaded.
"""

import asyncio
from typing import Optional

from .json_repair import extract_json, normalize_fields
from .jobs import TrackProgress
from .logging_config import logger
from .ocr import Cancelled, IsCancelled, file_to_images, ocr_pages_async, ocr_single_page

EXTRACTION_PROMPT = (
    "You are a KYC compliance assistant. First identify what kind of document this image "
    "is (passport, national ID, company registration certificate, address proof such as a "
    "utility bill or bank statement, etc.), then extract whatever key identity, company, or "
    "financial information is actually printed on it. Use exactly these snake_case keys, in "
    "this exact spelling and casing - do not invent new keys or rename them - and omit any "
    "key that does not apply: document_type, full_name, id_number, passport_number, "
    "date_of_birth, nationality, gender, address, company_name, registration_number, "
    "incorporation_date, issue_date, expiry_date, issuing_authority, place_of_birth, "
    "phone_number, email, bank_name, account_number.\n"
    "Only include a key if the document explicitly states that exact information for this "
    "document/person/company. Never guess, infer, or copy a different piece of information "
    "into an unrelated field (for example, do not put a company name into place_of_birth) - "
    "if something is not stated, omit the key entirely.\n"
    "Every value must be a single plain string, never an array or nested object - if a field "
    "like address spans multiple lines, join them into one string separated by commas.\n"
    "Respond with ONLY a single valid JSON object - no markdown code fences, no comments, no "
    "trailing commas. Every key and every string value must be wrapped in double quotes. Keep "
    "the JSON compact."
)


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
            parsed = normalize_fields(extract_json(raw))
            if not parsed:
                logger.warning("Could not parse any fields from %s page %d; raw response: %s", filename, i, raw[:500])
            for key, value in parsed.items():
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
