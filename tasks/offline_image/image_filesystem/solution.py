"""
Deterministic solution for the `image_filesystem` task using MCP servers.

This script:
1. 启动该任务的 Docker 环境（通过 TaskEnv + docker-compose）。
2. 通过 MCP-Universe 的 MCPManager 连接容器内的 `filesystem` 服务器（经 Gateway）。
3. 按照 ground truth 把图片移动到指定的三个目录：
   - /workspace/meme_data/comic_meme
   - /workspace/meme_data/animal_meme
   - /workspace/meme_data/human_meme
4. 调用本任务目录下的 evaluate.py 进行验证。

运行方式（在 MCPU-MM 根目录或本目录均可）:

    cd /Users/vichen/school/MCP/MCPU-MM
    source /Users/vichen/school/MCP/MCP-Universe/venv/bin/activate
    python tasks/offline_image/image_filesystem/solution.py
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Dict, Set

import sys
import httpx

from mcpuniverse.common.context import Context
from mcpuniverse.mcp.manager import MCPManager


# Ensure we can import the local `harness` package when running this file directly.
# When executed as `python tasks/offline_image/image_filesystem/solution.py`, sys.path[0] is
# this directory (`tasks/offline_image/image_filesystem`), so we need to add the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.task_env import TaskEnv


async def _wait_for_gateway_ready(
    gateway_url: str,
    max_retries: int = 30,
    delay: float = 0.5,
) -> None:
    """
    等待 Gateway 的 SSE 端点就绪（返回 200），避免过早连接导致 httpx.ReadError。
    """
    for _ in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                async with client.stream("GET", gateway_url) as response:
                    if response.status_code == 200:
                        return
        except httpx.ConnectError:
            # Gateway 还没起来，继续重试
            pass
        except Exception:
            # 其他错误也重试几次
            pass
        await asyncio.sleep(delay)
    raise RuntimeError(f"Gateway at {gateway_url} did not become ready after {max_retries} retries.")


async def _classify_with_filesystem_mcp(
    ground_truth: Dict[str, Set[str]],
    gateway_port: int,
) -> None:
    """
    使用 MCP filesystem server 在容器内完成目录创建与文件移动。

    Args:
        ground_truth: 例如 {"comic_meme": {"15120.jpg", ...}, "animal_meme": {...}, ...}
        gateway_port: Gateway 在宿主机暴露的端口（通常是 FILESYSTEM_MCP_PORT）
    """
    # 让 MCPManager 通过 Gateway 连接到 filesystem 服务器
    os.environ["MCP_GATEWAY_ADDRESS"] = f"http://127.0.0.1:{gateway_port}"

    context = Context()
    mcp_manager = MCPManager(context=context)

    # 只需要 filesystem 服务器，使用 SSE 传输，经 Gateway 转发到容器内 stdio server
    client = await mcp_manager.build_client("filesystem", transport="sse")
    try:
        # 0. 先测试创建一个 debug 目录，确认 server 有写权限、路径语义正确
        try:
            print("\n[DEBUG] Testing create_directory with 'meme_data/debug_dir'")
            test_res = await client.execute_tool(
                tool_name="create_directory",
                arguments={"path": "meme_data/debug_dir"},
            )
            print("[DEBUG] create_directory debug_dir result:", getattr(test_res, "content", None))
        except Exception as e:
            print(f"[DEBUG] create_directory debug_dir failed: {e}")

        # 1. 确保三个目标目录存在
        # filesystem MCP server 的根目录是 FILESYSTEM_DIRECTORY=/workspace，
        # 它期望收到的是“相对于根目录”的路径。
        # evaluate.py 在容器内检查的是 /workspace/meme_data/{folder}，
        # 因此这里传入相对路径 "meme_data/..."，两边刚好对齐。
        base_dir = "meme_data"
        for folder in ground_truth.keys():
            target_dir = f"{base_dir}/{folder}"
            print(f"[DEBUG] create_directory {target_dir}")
            try:
                res = await client.execute_tool(
                    tool_name="create_directory",
                    arguments={"path": target_dir},
                )
                print("[DEBUG]   result:", getattr(res, "content", None))
            except Exception as e:
                print(f"[DEBUG]   create_directory {target_dir} failed: {e}")

        # 2. 按照 ground truth 把图片移动到对应目录
        for folder, files in ground_truth.items():
            for fname in files:
                src = f"{base_dir}/{fname}"
                dst = f"{base_dir}/{folder}/{fname}"
                print(f"[DEBUG] move_file {src} -> {dst}")
                try:
                    res = await client.execute_tool(
                        tool_name="move_file",
                        arguments={
                            "source": src,
                            "destination": dst,
                        },
                    )
                    print("[DEBUG]   result:", getattr(res, "content", None))
                except Exception as e:
                    print(f"[DEBUG]   move_file {src} -> {dst} failed: {e}")
    finally:
        await client.cleanup()


async def main() -> None:
    # 任务目录
    task_dir = Path(__file__).resolve().parent

    # 从 evaluate.py 复用 ground truth 与 verify 函数
    from evaluate import GROUND_TRUTH, verify  # type: ignore

    # 启动该任务的 Docker 环境
    env = TaskEnv(
        task_dir=task_dir,
        name="image_filesystem",
        compose_path=task_dir / "docker-compose.yaml",
    )

    with env.spin_up():
        # 获得 MCP 服务器端口映射信息
        port_mapping = env.get_mcp_server_ports()
        if "filesystem" not in port_mapping:
            # 解析 docker-compose 失败时，退回到环境变量配置
            filesystem_port = int(os.environ.get("FILESYSTEM_MCP_PORT", "3333"))
            port_mapping["filesystem"] = filesystem_port

        gateway_port = port_mapping["filesystem"]

        # 在通过 Gateway 连接 SSE 之前，先等待其就绪，避免 httpx.ReadError
        gateway_sse_url = f"http://127.0.0.1:{gateway_port}/filesystem/sse"
        await _wait_for_gateway_ready(gateway_sse_url)

        # 使用 MCP filesystem server 在容器内完成分类与文件移动
        await _classify_with_filesystem_mcp(
            ground_truth=GROUND_TRUTH,
            gateway_port=gateway_port,
        )

        # 为了 debug，先在容器里看一下 /workspace 以及 /workspace/meme_data 的实际结构
        container_name = env.get_container_name()
        print("\n=== DEBUG: Container filesystem after classification ===")
        try:
            print(f"[DEBUG] docker exec {container_name} ls -R /workspace")
            subprocess.run(
                ["docker", "exec", container_name, "sh", "-lc", "ls -R /workspace"],
                check=False,
            )
            print("\n[DEBUG] docker exec {container} ls -R /workspace/meme_data".format(
                container=container_name
            ))
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "sh",
                    "-lc",
                    "ls -R /workspace/meme_data || echo 'meme_data not found'",
                ],
                check=False,
            )
        except Exception as e:
            print(f"[DEBUG] Failed to inspect container filesystem: {e}")

        # 稍微等一等，确保所有文件操作落盘
        await asyncio.sleep(1.0)

        # 使用已有的 evaluate.py 进行验证
        passed, reason = verify(task_dir, container_name=container_name)

        print("=== Solution Evaluation ===")
        print("Passed:", passed)
        print("Reason:", reason)


if __name__ == "__main__":
    asyncio.run(main())


