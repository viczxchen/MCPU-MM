import json
from pathlib import Path
from typing import Any, Tuple


EXPECTED_CITY = "New York City"
EXPECTED_FOOD = "smoothie"
EXPECTED_INGREDIENTS = [
    "frozen spinach",
    "protein powder",
    "chia seeds",
    "ground flax seeds",
    "almond milk",
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

    city = _normalize_text(data.get("City"))
    food = _normalize_text(data.get("Food"))
    ingredients = data.get("What's in it?")

    if city != _normalize_text(EXPECTED_CITY):
        return False, f"Key 'City' mismatch: expected '{EXPECTED_CITY}', got '{data.get('City', '')}'"
    if food != _normalize_text(EXPECTED_FOOD):
        return False, f"Key 'Food' mismatch: expected '{EXPECTED_FOOD}', got '{data.get('Food', '')}'"
    if not isinstance(ingredients, list):
        return False, "Key \"What's in it?\" must be a list of strings."

    normalized_actual = [_normalize_text(item) for item in ingredients]
    normalized_expected = [_normalize_text(item) for item in EXPECTED_INGREDIENTS]
    if normalized_actual != normalized_expected:
        return (
            False,
            f'Key "What\'s in it?" mismatch: expected {EXPECTED_INGREDIENTS}, got {ingredients}',
        )

    return True, "Exact JSON match passed"
