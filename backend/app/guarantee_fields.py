"""Extracts the key identifying fields of a Letter of Guarantee - guarantee
number, applicant, beneficiary, effective/expiry dates, and the Power of
Attorney clause - from the client letter. The client letter is treated as
the source of truth for these fields, since the whole point of the
comparison is checking whether Mizuho's letter matches it.

Runs as a vision prompt over the same rendered client page images used for
full-text OCR, the same way KYC field extraction works - not a text-only
prompt over the already-OCR'd text. GLM-OCR is an OCR-specialized vision
model; asking it to follow instructions over plain text with no image
attached is unreliable and was consistently returning nothing.
"""

import asyncio
from typing import Optional

from .json_repair import extract_json, normalize_fields
from .jobs import TrackProgress
from .logging_config import logger
from .ocr import Cancelled, IsCancelled, ocr_single_page

GUARANTEE_FIELDS_PROMPT = (
    "Look at this page of a bank Letter of Guarantee and extract the following as a "
    "single strict JSON object, using exactly these keys, and omit a key only if that "
    "information does not appear on this page:\n"
    "- guarantee_number: the guarantee/reference number, typically 3 uppercase letters "
    "followed by digits and dashes (e.g. GTO-768-500363-032)\n"
    "- applicant: the company or party being guaranteed for (usually introduced as "
    '"the Company")\n'
    "- beneficiary: the party the letter is addressed to / who receives the guarantee\n"
    "- effective_date: the date the guarantee takes effect (often the letter date at the top)\n"
    "- expiry_date: the date the guarantee expires\n"
    "- power_of_attorney: the exact sentence or clause referencing the Power of Attorney "
    "(its date and the signatory), copied verbatim from the page - do not paraphrase it\n\n"
    "Only include a key if this exact page states that information - do not guess or infer "
    "it from context. Every value must be a single plain string, never an array or nested "
    "object.\n"
    "Respond with ONLY the JSON object - no markdown code fences, no comments, no trailing "
    "commas. Every key and value must be double-quoted."
)


async def extract_guarantee_fields_async(
    pages: list,
    filename: str,
    is_cancelled: IsCancelled = None,
    track: Optional[TrackProgress] = None,
) -> dict:
    total = len(pages)
    if track is not None:
        track.total = total

    fields: dict = {}
    for i, page in enumerate(pages, start=1):
        if is_cancelled is not None and await is_cancelled():
            logger.info("Stopping key-info extraction for %s before page %d/%d (cancelled).", filename, i, total)
            raise Cancelled(f"Stopped before page {i}/{total}.")

        if track is not None:
            track.current = i

        raw = await asyncio.to_thread(
            ocr_single_page, page, GUARANTEE_FIELDS_PROMPT, page_label=f"{filename} key-info page {i}/{total}"
        )
        parsed = normalize_fields(extract_json(raw))
        if not parsed:
            logger.warning(
                "Could not parse guarantee fields from %s page %d; raw response: %s", filename, i, raw[:500]
            )
        for key, value in parsed.items():
            fields.setdefault(key, value)

    if track is not None:
        track.done = True

    logger.info(
        "Guarantee field extraction for %s found %d field(s): %s", filename, len(fields), sorted(fields.keys())
    )
    return fields
