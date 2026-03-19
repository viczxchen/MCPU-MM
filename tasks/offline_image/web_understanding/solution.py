from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.task_env import TaskEnv


async def _wait_for_site_ready(url: str, max_retries: int = 90) -> None:
    for _ in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError(f"Offline site is not reachable: {url}")


async def main() -> None:
    task_dir = Path(__file__).resolve().parent
    from evaluate import verify  # type: ignore

    env = TaskEnv(
        task_dir=task_dir,
        name="web_understanding",
        compose_path=task_dir / "docker-compose.yaml",
    )
    with env.spin_up():
        site_port = os.environ.get("WEB_UNDERSTANDING_PORT", "18080")
        await _wait_for_site_ready(f"http://127.0.0.1:{site_port}/amazon_sample.html")
        passed, reason = verify(
            task_dir,
            container_name=env.get_container_name(),
            agent_result="14.99",
        )
        print("Passed:", passed)
        print("Reason:", reason)


if __name__ == "__main__":
    asyncio.run(main())
