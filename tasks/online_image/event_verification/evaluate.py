from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

EXPECTED_EXACT: Dict[str, str] = {
    "Date": "2024-07-13",
    "State": "Pennsylvania",
    "City": "Butler",
}

EXPECTED_INFO_NUMBERS = {"2", "7"}
EXPECTED_INFO_KEYWORDS = {"death", "injur"}  # stem-like match: death/deaths, injure/injured/injuries


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_json_object(text: str) -> Optional[Dict[str, str]]:
    text = text.strip()
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

    direct = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if direct:
        candidate = direct.group(0)
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _check_info_fuzzy(info: str) -> Tuple[bool, str]:
    normalized = _normalize_text(info)
    numbers = set(re.findall(r"\d+", normalized))
    if not EXPECTED_INFO_NUMBERS.issubset(numbers):
        return False, "Info field missing expected numbers '2' and '7'"

    if not all(keyword in normalized for keyword in EXPECTED_INFO_KEYWORDS):
        return False, "Info field missing expected death/injury semantics"

    return True, "Info field fuzzy match passed"


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    parsed = _extract_json_object(agent_result)
    if parsed is None:
        return False, "Answer must be a JSON object with Date/State/City/Info"

    for key, expected_value in EXPECTED_EXACT.items():
        actual = parsed.get(key)
        if actual is None:
            return False, f"Missing key '{key}' in answer JSON"
        if _normalize_text(str(actual)) != _normalize_text(expected_value):
            return False, f"Key '{key}' mismatch: expected '{expected_value}', got '{actual}'"

    info = parsed.get("Info")
    if info is None:
        return False, "Missing key 'Info' in answer JSON"
    ok, reason = _check_info_fuzzy(str(info))
    if not ok:
        return False, reason

    return True, "Event verification JSON exact+fuzzy checks passed"
