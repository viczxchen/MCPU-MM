from pathlib import Path
import re
from typing import Tuple

EXPECTED_ANSWER = "14.99"


def get_container_name(task_name: str) -> str:
    return f"mcpu-mm-web-understanding-{task_name}"


def _normalize_answer(answer: str) -> str:
    """
    Normalize agent answer so small format differences don't fail exact-value intent.
    Examples:
      "$14.99" -> "14.99"
      "The price is 14.99 USD." -> "14.99"
    """
    stripped = answer.strip()
    if not stripped:
        return stripped

    # If a price-like number exists, use the first one.
    match = re.search(r"\d+(?:\.\d+)?", stripped)
    if match:
        return match.group(0)
    return stripped


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    _ = test_dir
    _ = container_name

    answer = _normalize_answer(agent_result)
    if answer != EXPECTED_ANSWER:
        return False, f"Expected '{EXPECTED_ANSWER}', got '{answer or '<empty>'}'"
    return True, "Answer matches expected value"
