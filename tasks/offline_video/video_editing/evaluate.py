import json
import subprocess
from pathlib import Path
from typing import Tuple

EXPECTED_FILE = "truman_single_person.mp4"


def _file_ok_in_container(container_name: str, rel_path: str) -> Tuple[bool, str]:
    """Check file exists and is non-empty inside the task container (agent writes to /workspace)."""
    in_container = f"/workspace/{rel_path}"
    stat = subprocess.run(
        ["docker", "exec", container_name, "stat", "-c", "%s", in_container],
        capture_output=True,
        text=True,
        check=False,
    )
    if stat.returncode != 0:
        return False, f"Missing expected output file in container: {in_container}"
    try:
        size = int(stat.stdout.strip())
    except ValueError:
        return False, f"Could not stat output file in container: {in_container}"
    if size <= 0:
        return False, f"Output file is empty in container: {in_container}"
    return True, ""


def verify(
    test_dir: Path,
    container_name: str = None,
    agent_result: str = "",
) -> Tuple[bool, str]:
    if container_name:
        ok, err = _file_ok_in_container(container_name, EXPECTED_FILE)
        if not ok:
            return False, err
    else:
        target = test_dir / EXPECTED_FILE
        if not target.exists():
            return False, f"Missing expected output file: {EXPECTED_FILE}"
        if target.stat().st_size <= 0:
            return False, f"Output file is empty: {EXPECTED_FILE}"

    if agent_result.strip():
        try:
            parsed = json.loads(agent_result)
            out = str(parsed.get("output_file", "")).strip()
            if out and out != EXPECTED_FILE:
                return False, f"Expected output_file '{EXPECTED_FILE}', got '{out}'"
        except json.JSONDecodeError:
            return False, "Agent result is not valid JSON"

    return True, "Edited clip exists"
