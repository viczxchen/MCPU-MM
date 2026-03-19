from pathlib import Path
import subprocess
from typing import Tuple

EXPECTED_ANSWER = "Yes"


def get_container_name(task_name: str) -> str:
    return f"mcpu-mm-shopping-information-{task_name}"


def verify(test_dir: Path, container_name: str = None) -> Tuple[bool, str]:
    if container_name is None:
        container_name = get_container_name(test_dir.name)

    result = subprocess.run(
        ["docker", "exec", container_name, "cat", "/workspace/answer.txt"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, "Missing /workspace/answer.txt"

    answer = result.stdout.strip()
    if answer != EXPECTED_ANSWER:
        return False, f"Expected '{EXPECTED_ANSWER}', got '{answer}'"
    return True, "Answer matches expected value"
