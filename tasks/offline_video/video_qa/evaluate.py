import json
from pathlib import Path
from typing import Any, Dict, Tuple

EXPECTED = {
    "prediction 1": "expertise will be near free",
    "prediction 2": "labor will be near free",
    "prediction 3": "computer use will grow expansively",
}


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _extract_json(agent_result: str) -> Dict[str, Any] | None:
    """Same strategy as online_video tasks: allow JSON embedded in extra prose."""
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

    if not agent_result.strip():
        return False, "Empty answer"

    parsed = _extract_json(agent_result)
    if parsed is None:
        return False, "Expected JSON object in the final answer (could not parse JSON)."

    for key, expected_value in EXPECTED.items():
        actual = parsed.get(key, "")
        if _norm(str(actual)) != _norm(expected_value):
            return False, f"Mismatch for '{key}': expected '{expected_value}', got '{actual}'"

    return True, "Answer matches expected predictions"
