"""GLM-OCR client.

Talks to Ollama's *native* ``/api/chat`` endpoint rather than the OpenAI-compatible
``/v1/chat/completions`` route. This matters: the OpenAI-compatible route does not
honor Ollama's ``options`` block (``num_ctx`` / ``num_predict``), so a page image
that consumes most of the (small, default) context window leaves almost no budget
for output tokens and generation stops after a line or two -- which is exactly the
"output.md only has each page's first line" symptom. The native endpoint applies
``options`` correctly, and also takes images as a top-level base64 list on the
message instead of an OpenAI-style ``image_url`` content block.
"""

import base64
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from pdf2image import convert_from_bytes

from .config import settings


class OCRError(Exception):
    pass


DEFAULT_OCR_PROMPT = (
    "Transcribe every word visible on this document page into clean Markdown. "
    "Preserve headings, tables, labels, values, numbers, and layout order exactly as "
    "written. Do not summarize, paraphrase, omit, or reword anything, and do not stop "
    "until the entire page - including footers and small print - has been transcribed."
)


def _encode_image(pil_image: Image.Image) -> str:
    buf = BytesIO()
    pil_image.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def file_to_images(filename: str, file_bytes: bytes, dpi: int = None) -> list:
    dpi = dpi or settings.OCR_DPI
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            return convert_from_bytes(file_bytes, dpi=dpi)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as OCRError
            raise OCRError(f"Could not render PDF pages: {exc}") from exc

    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise OCRError(f"Could not read image file: {exc}") from exc
    return [image]


def ocr_single_page(pil_image: Image.Image, prompt: str = None) -> str:
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
        },
    }

    url = f"{settings.OLLAMA_URL.rstrip('/')}/api/chat"

    try:
        response = requests.post(url, json=payload, timeout=settings.OCR_TIMEOUT)
    except requests.RequestException as exc:
        raise OCRError(
            f"Could not reach GLM-OCR at {settings.OLLAMA_URL}. Is Ollama running "
            f"and reachable from the backend container? ({exc})"
        ) from exc

    if response.status_code != 200:
        raise OCRError(f"OCR backend error ({response.status_code}): {response.text[:500]}")

    data = response.json()
    content = (data.get("message") or {}).get("content", "")
    if not content.strip():
        raise OCRError("OCR backend returned an empty response for this page.")
    return content.strip()


def ocr_document(filename: str, file_bytes: bytes, prompt: str = None) -> dict:
    pages = file_to_images(filename, file_bytes)
    page_texts = [ocr_single_page(page, prompt) for page in pages]

    if len(page_texts) > 1:
        full_text = "\n\n".join(
            f"<!-- Page {i} -->\n\n{text}" for i, text in enumerate(page_texts, start=1)
        )
    else:
        full_text = page_texts[0] if page_texts else ""

    return {"pages": page_texts, "text": full_text.strip(), "page_count": len(pages)}
