from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

EXPECTED_ANSWER = "dodecagon"


def _normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"^(the|a|an)\s+", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    normalized = _normalize_text(agent_result)
    # Fuzzy rule requested by task owner:
    # pass when the final answer contains "dodecagon" anywhere.
    if EXPECTED_ANSWER in normalized:
        return True, "Fuzzy match passed: contains 'dodecagon'"

    return False, f"Expected answer containing '{EXPECTED_ANSWER}', got '{normalized or '<empty>'}'"
