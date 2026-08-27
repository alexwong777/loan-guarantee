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
_CAMEL_BOUNDARY_RE = re.compile(r"(?<!^)(?=[A-Z])")
_EMPTY_VALUES = {"", "n/a", "null", "none", "-"}


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


def _to_snake_case(key: str) -> str:
    if "_" in key or key.islower():
        return key.lower()
    return _CAMEL_BOUNDARY_RE.sub("_", key).lower()


def _stringify(value) -> str:
    """Coerces a parsed JSON value into a plain, readable string. The model is
    asked for flat strings but sometimes returns a number, or a nested
    list/object (e.g. a multi-line address as separate array entries) -
    without this, that shows up in the UI as the literal text
    "[object Object]"."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(s for s in (_stringify(v) for v in value) if s)
    if isinstance(value, dict):
        return ", ".join(s for s in (_stringify(v) for v in value.values()) if s)
    return "" if value is None else str(value)


def normalize_fields(raw: dict) -> dict:
    """Normalizes a parsed field dict: keys to snake_case (the model
    occasionally answers in camelCase for a subset of fields, which would
    otherwise show up as separate duplicate-looking entries), values coerced
    to plain strings, and empty/placeholder values dropped. Keeps the first
    value seen for a given key."""
    normalized: dict = {}
    for key, value in raw.items():
        clean_key = _to_snake_case(str(key))
        clean_value = _stringify(value)
        if not clean_value or clean_value.lower() in _EMPTY_VALUES:
            continue
        normalized.setdefault(clean_key, clean_value)
    return normalized
