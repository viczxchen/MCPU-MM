from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

EXPECTED_KEYWORDS = ("land", "rover", "freelander", "lr2", "hse")


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    normalized = _normalize_text(agent_result)
    if not normalized:
        return False, "Empty answer"

    missing = [kw for kw in EXPECTED_KEYWORDS if kw not in normalized]
    if missing:
        return False, f"Fuzzy match failed, missing keywords: {', '.join(missing)}"

    return True, "Fuzzy match passed for expected vehicle model keywords"
