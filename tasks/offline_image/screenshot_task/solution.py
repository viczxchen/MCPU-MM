from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx
from mcpuniverse.common.context import Context
from mcpuniverse.mcp.manager import MCPManager

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.task_env import TaskEnv

GROUND_TRUTH = {
    "images": ["WechatIMG157.jpg", "WechatIMG159.jpg"],
    "others": ["2019年中国科学院文献情报中心期刊分区表.xlsx", "World's Hardest CAPTCHA.html"],
    "videos": ["SaveTwitter.Net_21YmrFdXteYprS3a_(568p).mp4", "SaveTwitter.Net_G8GZZ7-bAAAXFSe_(gif).mp4"],
}


async def _wait_for_gateway_ready(gateway_url: str, max_retries: int = 30) -> None:
    for _ in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                async with client.stream("GET", gateway_url) as response:
                    if response.status_code == 200:
                        return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("Gateway not ready")


async def main() -> None:
    task_dir = Path(__file__).resolve().parent
    from evaluate import verify  # type: ignore

    env = TaskEnv(task_dir=task_dir, name="screenshot_task", compose_path=task_dir / "docker-compose.yaml")

    with env.spin_up():
        os.environ["MCP_GATEWAY_ADDRESS"] = f"http://127.0.0.1:{os.environ.get('FILESYSTEM_MCP_PORT', '3333')}"
        await _wait_for_gateway_ready(f"{os.environ['MCP_GATEWAY_ADDRESS']}/filesystem/sse")

        manager = MCPManager(context=Context())
        client = await manager.build_client("filesystem", transport="sse")
        try:
            for folder in GROUND_TRUTH:
                await client.execute_tool("create_directory", {"path": folder})
            for folder, files in GROUND_TRUTH.items():
                for filename in files:
                    await client.execute_tool(
                        "move_file",
                        {"source": filename, "destination": f"{folder}/{filename}"},
                    )
        finally:
            await client.cleanup()

        passed, reason = verify(task_dir, container_name=env.get_container_name())
        print("Passed:", passed)
        print("Reason:", reason)


if __name__ == "__main__":
    asyncio.run(main())
