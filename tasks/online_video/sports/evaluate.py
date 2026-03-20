import json
from pathlib import Path
from typing import Any, Tuple


EXPECTED_SCORE = "24-26"
EXPECTED_WINNER = "Japan"


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

    score = _normalize_text(data.get("score"))
    winner = _normalize_text(data.get("winner"))

    if score != _normalize_text(EXPECTED_SCORE):
        return False, f"Key 'score' mismatch: expected '{EXPECTED_SCORE}', got '{data.get('score', '')}'"
    if winner != _normalize_text(EXPECTED_WINNER):
        return False, f"Key 'winner' mismatch: expected '{EXPECTED_WINNER}', got '{data.get('winner', '')}'"

    return True, "Exact JSON match passed"
