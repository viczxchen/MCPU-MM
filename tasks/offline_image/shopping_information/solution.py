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

    env = TaskEnv(task_dir=task_dir, name="shopping_information", compose_path=task_dir / "docker-compose.yaml")
    with env.spin_up():
        os.environ["MCP_GATEWAY_ADDRESS"] = f"http://127.0.0.1:{os.environ.get('FILESYSTEM_MCP_PORT', '3333')}"
        await _wait_for_gateway_ready(f"{os.environ['MCP_GATEWAY_ADDRESS']}/filesystem/sse")

        manager = MCPManager(context=Context())
        client = await manager.build_client("filesystem", transport="sse")
        try:
            await client.execute_tool(
                tool_name="write_file",
                arguments={"path": "answer.txt", "content": "Yes"},
            )
        finally:
            await client.cleanup()

        passed, reason = verify(task_dir, container_name=env.get_container_name())
        print("Passed:", passed)
        print("Reason:", reason)


if __name__ == "__main__":
    asyncio.run(main())
