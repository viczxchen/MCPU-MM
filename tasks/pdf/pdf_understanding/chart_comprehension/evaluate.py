from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

EXPECTED_ANSWER = "Qwen2.5-VL (32B)"


def _normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    if not agent_result or not agent_result.strip():
        return False, "Empty answer"

    got = _normalize_text(agent_result)
    exp = _normalize_text(EXPECTED_ANSWER)
    if got != exp:
        return False, f"Expected exact match {exp!r}, got {got!r}"
    return True, "Answer matches expected judge label"
