from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple

EXPECTED: dict[str, Any] = {
    "title": "WebWatcher: Breaking New Frontiers of Vision-Language Deep Research Agent",
    "corresponding author": ["Xinyu Wang", "Yong Jiang"],
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


def _norm_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val]
    return [str(val).strip()]


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

    for key, expected in EXPECTED.items():
        actual = parsed.get(key)
        if key == "corresponding author":
            if _norm_list(actual) != _norm_list(expected):
                return False, f"Mismatch for '{key}': expected {expected!r}, got {actual!r}"
        else:
            if str(actual).strip() != str(expected).strip():
                return False, f"Mismatch for '{key}': expected {expected!r}, got {actual!r}"

    return True, "JSON matches expected title and corresponding authors"
