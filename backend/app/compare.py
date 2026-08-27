"""Word-level diff between the client letter and the Mizuho letter."""

import re
from difflib import SequenceMatcher

_TOKEN_RE = re.compile(r"\S+|\s+")


def _tokenize(text: str) -> list:
    return _TOKEN_RE.findall(text)


def compare_documents(client_text: str, mizuho_text: str) -> dict:
    client_tokens = _tokenize(client_text)
    mizuho_tokens = _tokenize(mizuho_text)

    matcher = SequenceMatcher(a=client_tokens, b=mizuho_tokens, autojunk=False)
    match_percentage = round(matcher.ratio() * 100, 1)

    left_segments = []
    right_segments = []
    discrepancies = []

    for opcode, a1, a2, b1, b2 in matcher.get_opcodes():
        left_text = "".join(client_tokens[a1:a2])
        right_text = "".join(mizuho_tokens[b1:b2])

        if opcode == "equal":
            if left_text:
                left_segments.append({"text": left_text, "type": "equal"})
            if right_text:
                right_segments.append({"text": right_text, "type": "equal"})
            continue

        if opcode == "delete":
            left_segments.append({"text": left_text, "type": "removed"})
        elif opcode == "insert":
            right_segments.append({"text": right_text, "type": "added"})
        elif opcode == "replace":
            left_segments.append({"text": left_text, "type": "removed"})
            right_segments.append({"text": right_text, "type": "added"})

        if left_text.strip() or right_text.strip():
            discrepancies.append(
                {
                    "type": opcode,
                    "client_text": left_text.strip(),
                    "mizuho_text": right_text.strip(),
                }
            )

    return {
        "match_percentage": match_percentage,
        "left_segments": left_segments,
        "right_segments": right_segments,
        "discrepancies": discrepancies,
    }
