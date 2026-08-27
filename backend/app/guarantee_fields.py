"""Extracts the key identifying fields of a Letter of Guarantee - guarantee
number, applicant, beneficiary, effective/expiry dates, and the Power of
Attorney clause - from the client letter's already-OCR'd text. The client
letter is treated as the source of truth for these fields, since the whole
point of the comparison is checking whether Mizuho's letter matches it.

This runs as a plain text prompt against the same GLM-OCR model (no image),
so it's a quick call on top of the OCR work that's already been done.
"""

import requests

from .config import settings
from .json_repair import extract_json
from .logging_config import logger

MAX_INPUT_CHARS = 12000

GUARANTEE_FIELDS_PROMPT = (
    "You are reviewing the OCR'd text of a bank Letter of Guarantee below. Extract the "
    "following as a single strict JSON object, using exactly these keys, and omit a key "
    "only if that information genuinely is not present in the text:\n"
    "- guarantee_number: the guarantee/reference number, typically 3 uppercase letters "
    "followed by digits and dashes (e.g. GTO-768-500363-032)\n"
    "- applicant: the company or party being guaranteed for (usually introduced as "
    '"the Company")\n'
    "- beneficiary: the party the letter is addressed to / who receives the guarantee\n"
    "- effective_date: the date the guarantee takes effect (often the letter date at the top)\n"
    "- expiry_date: the date the guarantee expires\n"
    "- power_of_attorney: the exact sentence or clause referencing the Power of Attorney "
    "(its date and the signatory), copied verbatim from the text - do not paraphrase it\n\n"
    "Respond with ONLY the JSON object - no markdown code fences, no comments, no trailing "
    "commas. Every key and value must be double-quoted.\n\nTEXT:\n"
)


def extract_guarantee_fields(client_text: str) -> dict:
    text = client_text.strip()
    if not text:
        return {}

    payload = {
        "model": settings.OCR_MODEL,
        "stream": False,
        "messages": [
            {"role": "user", "content": GUARANTEE_FIELDS_PROMPT + text[:MAX_INPUT_CHARS]}
        ],
        "options": {
            "num_ctx": settings.OCR_NUM_CTX,
            "num_predict": 1024,
            "temperature": 0.1,
            "repeat_penalty": 1.3,
            "repeat_last_n": 256,
        },
    }
    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/chat"

    try:
        response = requests.post(url, json=payload, timeout=settings.OCR_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Guarantee field extraction request failed: %s", exc)
        return {}

    content = (response.json().get("message") or {}).get("content", "")
    fields = extract_json(content)
    if not fields:
        logger.warning("Could not parse guarantee fields from response: %s", content[:500])

    return {k: v for k, v in fields.items() if v not in (None, "", "N/A", "n/a", "null")}
