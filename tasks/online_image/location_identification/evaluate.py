from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

EXPECTED: Dict[str, str] = {
    "Country": "Japan",
    "City": "Kobe",
    "Location": "Kobe University Centennial Hall",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_json_object(text: str) -> Optional[Dict[str, str]]:
    text = text.strip()
    if not text:
        return None

    # Prefer fenced json block if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

    # Fallback to first {...} block.
    direct = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if direct:
        candidate = direct.group(0)
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    parsed = _extract_json_object(agent_result)
    if parsed is not None:
        for key, expected_value in EXPECTED.items():
            actual = parsed.get(key)
            if actual is None:
                return False, f"Missing key '{key}' in answer JSON"
            if _normalize_text(str(actual)) != _normalize_text(expected_value):
                return False, f"Key '{key}' mismatch: expected '{expected_value}', got '{actual}'"
        return True, "Location JSON fields match expected answer"

    # Backward-compatible fallback: accept a single-line "<country>, <city>, <location>" answer.
    normalized = _normalize_text(agent_result)
    expected_line = _normalize_text(
        f"{EXPECTED['Country']}, {EXPECTED['City']}, {EXPECTED['Location']}"
    )
    if normalized == expected_line:
        return True, "Location text answer matches expected value"

    return False, "Answer is neither valid expected JSON nor exact location text"
