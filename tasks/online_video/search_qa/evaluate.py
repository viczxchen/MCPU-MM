import json
from pathlib import Path
from typing import Any, Tuple


EXPECTED_OFFICE_HOUR = "Monday 2-4 pm"
EXPECTED_BOOK_KEYWORD = "calendly"


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

    office_hour = _normalize_text(data.get("Office Hour"))
    book_via = _normalize_text(data.get("Book via"))

    if office_hour != _normalize_text(EXPECTED_OFFICE_HOUR):
        return (
            False,
            f"Key 'Office Hour' mismatch: expected '{EXPECTED_OFFICE_HOUR}', got '{data.get('Office Hour', '')}'",
        )

    if EXPECTED_BOOK_KEYWORD not in book_via:
        return (
            False,
            f"Key 'Book via' fuzzy mismatch: expected to contain '{EXPECTED_BOOK_KEYWORD}', got '{data.get('Book via', '')}'",
        )

    return True, "Exact+fuzzy JSON match passed"
