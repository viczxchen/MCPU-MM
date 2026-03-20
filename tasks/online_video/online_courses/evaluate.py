import json
from pathlib import Path
from typing import Any, Tuple


EXPECTED_TITLES = [
    "Scaling Laws for Neural Language Models",
    "Language Models are Few-Shot Learners",
]


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_json(agent_result: str) -> dict | None:
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
    test_dir: str | Path,
    container_name: str | None = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir, container_name

    data = _extract_json(agent_result)
    if data is None:
        return False, "Expected JSON object output, but failed to parse JSON."

    titles = data.get("title")
    if not isinstance(titles, list):
        return False, "Key 'title' must be a list of strings."

    normalized_actual = [_normalize_text(item) for item in titles]
    normalized_expected = [_normalize_text(item) for item in EXPECTED_TITLES]
    if normalized_actual != normalized_expected:
        return False, f"Key 'title' mismatch: expected {EXPECTED_TITLES}, got {titles}"

    return True, "Exact JSON match passed"
