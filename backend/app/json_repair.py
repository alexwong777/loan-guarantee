"""Shared repair helpers for parsing LLM output that's *supposed* to be JSON but
often isn't quite - wrapped in markdown fences, unquoted keys, a stray quote
before a colon, cut off mid-string, trailing commas. Used by both KYC field
extraction and Letter of Guarantee key-field extraction.
"""

import json
import re

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


def extract_json(raw: str) -> dict:
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
