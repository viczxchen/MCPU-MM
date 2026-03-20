from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple

EXPECTED: dict[str, Any] = {
    "all_exist": False,
    "title": "Icu length-of-stay prediction with interaction-based explanations",
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


def _norm_title(s: str) -> str:
    return " ".join(s.strip().lower().split())


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

    exp_all = EXPECTED["all_exist"]
    act_all = parsed.get("all_exist")
    if isinstance(act_all, str):
        act_all = act_all.strip().lower() in ("true", "1", "yes")
    if bool(act_all) != bool(exp_all):
        return False, f"Expected all_exist={exp_all!r}, got {parsed.get('all_exist')!r}"

    exp_title = _norm_title(str(EXPECTED["title"]))
    act_title = _norm_title(str(parsed.get("title", "")))
    if act_title != exp_title:
        return False, f"Expected title (normalized) {exp_title!r}, got {act_title!r}"

    return True, "JSON matches expected citation verification result"
