from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple

EXPECTED: dict[str, str] = {
    "Result": "Incorrect",
    "Reason": "4.00%",
    "Correction": "5.00%",
}


def _extract_json(agent_result: str) -> dict[str, Any] | None:
    if not agent_result:
        return None
    text = agent_result.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    parsed = _extract_json(agent_result)
    if parsed is None:
        return False, "Expected JSON object in the final answer (could not parse JSON)."

    for key, exp in EXPECTED.items():
        act = parsed.get(key)
        if str(act).strip() != str(exp).strip():
            return False, f"Mismatch for '{key}': expected {exp!r}, got {act!r}"

    return True, "JSON matches expected verification result"
