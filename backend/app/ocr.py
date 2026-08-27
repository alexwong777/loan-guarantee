"""GLM-OCR client.

Talks to Ollama's *native* ``/api/chat`` endpoint rather than the OpenAI-compatible
``/v1/chat/completions`` route. This matters: the OpenAI-compatible route does not
honor Ollama's ``options`` block (``num_ctx`` / ``num_predict``), so a page image
that consumes most of the (small, default) context window leaves almost no budget
for output tokens and generation stops after a line or two -- which is exactly the
"output.md only has each page's first line" symptom. The native endpoint applies
``options`` correctly, and also takes images as a top-level base64 list on the
message instead of an OpenAI-style ``image_url`` content block.

Page calls run through ``asyncio.to_thread`` so a slow OCR call doesn't block the
whole event loop (and so the caller can check for cancellation between pages).
"""

import asyncio
import base64
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Awaitable, Callable, Optional

import requests
from PIL import Image
from pdf2image import convert_from_bytes

from .config import settings
from .jobs import TrackProgress
from .logging_config import logger

IsCancelled = Optional[Callable[[], Awaitable[bool]]]


class OCRError(Exception):
    pass


class Cancelled(OCRError):
    """Raised when the client stops the job before all pages finish."""


DEFAULT_OCR_PROMPT = (
    "Transcribe every word visible on this document page into clean Markdown. "
    "Preserve headings, tables, labels, values, numbers, and layout order exactly as "
    "written. Do not summarize, paraphrase, omit, or reword anything, and do not stop "
    "until the entire page - including footers and small print - has been transcribed. "
    "Write each line once; never repeat a line, sentence, or paragraph."
)


def _encode_image(pil_image: Image.Image) -> str:
    buf = BytesIO()
    pil_image.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _dedupe_repeats(text: str) -> str:
    """Vision-language OCR occasionally loops and repeats a line or paragraph
    verbatim before it recovers. Collapse immediate consecutive repeats at both
    the line and paragraph level as a safety net on top of the anti-repeat
    generation options."""
    lines = text.split("\n")
    deduped_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and deduped_lines and deduped_lines[-1].strip() == stripped:
            continue
        deduped_lines.append(line)

    blocks = re.split(r"\n\s*\n", "\n".join(deduped_lines))
    deduped_blocks = []
    for block in blocks:
        stripped = block.strip()
        if stripped and deduped_blocks and deduped_blocks[-1].strip() == stripped:
            continue
        deduped_blocks.append(block)

    return "\n\n".join(deduped_blocks)


def file_to_images(filename: str, file_bytes: bytes, dpi: int = None) -> list:
    dpi = dpi or settings.OCR_DPI
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            pages = convert_from_bytes(file_bytes, dpi=dpi)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as OCRError
            logger.exception("Failed to render PDF pages for %s", filename)
            raise OCRError(f"Could not render PDF pages: {exc}") from exc
        # pdf2image's returned images are backed by files in a temp directory
        # that can be cleaned up once this function returns. Force a full
        # decode into memory now, while we're still single-threaded - callers
        # may later read these same Image objects concurrently from multiple
        # threads (e.g. KYC extraction runs a fields pass and a full-text pass
        # in parallel), and a still-lazy Image being loaded from two threads
        # at once against an already-vanished temp file raises
        # "image file is truncated".
        for page in pages:
            page.load()
        logger.info("Rendered %s -> %d page(s) at %d DPI", filename, len(pages), dpi)
        return pages

    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to read image file %s", filename)
        raise OCRError(f"Could not read image file: {exc}") from exc
    return [image]


def ocr_single_page(pil_image: Image.Image, prompt: str = None, page_label: str = "page") -> str:
    prompt = prompt or DEFAULT_OCR_PROMPT
    img_b64 = _encode_image(pil_image)

    payload = {
        "model": settings.OCR_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_b64],
            }
        ],
        "options": {
            "num_ctx": settings.OCR_NUM_CTX,
            "num_predict": settings.OCR_NUM_PREDICT,
            "temperature": 0.1,
            # Discourages the model from getting stuck looping the same
            # line/paragraph, which otherwise shows up as duplicated text
            # in the OCR output.
            "repeat_penalty": 1.3,
            "repeat_last_n": 256,
        },
    }

    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/chat"

    logger.info(
        "OCR request: %s -> %s (model=%s, num_ctx=%d, num_predict=%d, timeout=%ds)",
        page_label, url, settings.OCR_MODEL, settings.OCR_NUM_CTX, settings.OCR_NUM_PREDICT,
        settings.OCR_TIMEOUT,
    )
    started = time.monotonic()

    try:
        response = requests.post(url, json=payload, timeout=settings.OCR_TIMEOUT)
    except requests.RequestException as exc:
        logger.error("OCR request for %s failed after %.1fs: %s", page_label, time.monotonic() - started, exc)
        raise OCRError(
            f"Could not reach GLM-OCR at {settings.OLLAMA_URL}. Is Ollama running "
            f"and reachable from the backend container? ({exc})"
        ) from exc

    elapsed = time.monotonic() - started

    if response.status_code != 200:
        logger.error(
            "OCR request for %s returned %d after %.1fs: %s",
            page_label, response.status_code, elapsed, response.text[:500],
        )
        raise OCRError(f"OCR backend error ({response.status_code}): {response.text[:500]}")

    data = response.json()
    content = (data.get("message") or {}).get("content", "")
    if not content.strip():
        logger.error("OCR request for %s returned an empty response after %.1fs", page_label, elapsed)
        raise OCRError("OCR backend returned an empty response for this page.")

    content = _dedupe_repeats(content.strip())
    logger.info("OCR request for %s succeeded in %.1fs (%d chars)", page_label, elapsed, len(content))
    return content


def _assemble_result(page_texts: list) -> dict:
    if len(page_texts) > 1:
        full_text = "\n\n".join(
            f"<!-- Page {i} -->\n\n{text}" for i, text in enumerate(page_texts, start=1)
        )
    else:
        full_text = page_texts[0] if page_texts else ""

    return {"pages": page_texts, "text": full_text.strip(), "page_count": len(page_texts)}


async def ocr_pages_async(
    pages: list,
    filename: str,
    prompt: str = None,
    is_cancelled: IsCancelled = None,
    track: Optional[TrackProgress] = None,
) -> dict:
    total = len(pages)
    if track is not None:
        track.total = total

    page_texts = []
    for i, page in enumerate(pages, start=1):
        if is_cancelled is not None and await is_cancelled():
            logger.info("Stopping %s before page %d/%d (cancelled).", filename, i, total)
            raise Cancelled(f"Stopped before page {i}/{total}.")

        if track is not None:
            track.current = i

        text = await asyncio.to_thread(
            ocr_single_page, page, prompt, page_label=f"{filename} page {i}/{total}"
        )
        page_texts.append(text)

    if track is not None:
        track.done = True

    return _assemble_result(page_texts)


async def ocr_document_async(
    filename: str,
    file_bytes: bytes,
    prompt: str = None,
    is_cancelled: IsCancelled = None,
    track: Optional[TrackProgress] = None,
) -> dict:
    pages = file_to_images(filename, file_bytes)
    return await ocr_pages_async(pages, filename, prompt=prompt, is_cancelled=is_cancelled, track=track)
