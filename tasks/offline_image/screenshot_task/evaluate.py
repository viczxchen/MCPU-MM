from pathlib import Path
import subprocess
from typing import Dict, Set, Tuple

GROUND_TRUTH: Dict[str, Set[str]] = {
    "images": {"WechatIMG157.jpg", "WechatIMG159.jpg"},
    "others": {
        "2019年中国科学院文献情报中心期刊分区表.xlsx",
        "World's Hardest CAPTCHA.html",
    },
    "videos": {
        "SaveTwitter.Net_21YmrFdXteYprS3a_(568p).mp4",
        "SaveTwitter.Net_G8GZZ7-bAAAXFSe_(gif).mp4",
    },
}


def get_container_name(task_name: str) -> str:
    return f"mcpu-mm-screenshot-task-{task_name}"


def _list_files(container_name: str, folder: str) -> Set[str]:
    result = subprocess.run(
        ["docker", "exec", container_name, "find", f"/workspace/initial_state/{folder}", "-maxdepth", "1", "-type", "f"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {Path(line).name for line in result.stdout.splitlines() if line.strip()}


def _dir_exists(container_name: str, path: str) -> bool:
    result = subprocess.run(
        ["docker", "exec", container_name, "test", "-d", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def verify(test_dir: Path, container_name: str = None) -> Tuple[bool, str]:
    if container_name is None:
        container_name = get_container_name(test_dir.name)

    errors = []
    root_level_folders = []
    for folder, expected in GROUND_TRUTH.items():
        init_state_dir = f"/workspace/initial_state/{folder}"
        root_dir = f"/workspace/{folder}"
        if not _dir_exists(container_name, init_state_dir):
            errors.append(f"Missing folder: {folder}")
            if _dir_exists(container_name, root_dir):
                root_level_folders.append(folder)
            continue

        actual = _list_files(container_name, folder)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing:
                errors.append(f"{folder} missing: {', '.join(missing)}")
            if extra:
                errors.append(f"{folder} extra: {', '.join(extra)}")

    if errors:
        if root_level_folders:
            errors.append(
                "Detected folders at /workspace/{0}; expected under /workspace/initial_state/{0}".format(
                    ",".join(sorted(root_level_folders))
                )
            )
        return False, "; ".join(errors)
    return True, "Folder structure matches ground truth"
