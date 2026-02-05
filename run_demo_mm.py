"""
Run a single demo task using MCP-Universe ReAct agent inside an isolated Docker env.

Usage (from the MCPU-MM directory, with MCP-Universe installed in the env):

    python -m MCPU_MM.run_demo_mm
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from mcpuniverse.agent.react import ReAct
from mcpuniverse.common.context import Context
from mcpuniverse.llm.openai import OpenAIModel, OpenAIConfig
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.callbacks.handlers.vprint import get_vprint_callbacks

from harness import LiteRunner, LiteTaskSpec


def _load_env_file(env_path: Path) -> None:
    """
    Load key=value pairs from a .env file into os.environ (if not already set).
    This keeps run_demo_mm.py free of hard-coded paths/ports.
    """
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Do not override already-exported environment variables
        os.environ.setdefault(key, value)


async def main() -> None:
    # Set up logging to show verbose output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(process)d %(name)s %(levelname)s [%(funcName)s():%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S,%f",
    )
    
    # 1. Locate demo task directory
    project_root = Path(__file__).resolve().parent
    task_dir = project_root / "tasks" / "image_filesystem"

    # Load environment variables from .env at project root (if present)
    _load_env_file(project_root / ".env")

    # For this local demo, ALWAYS force Gateway to point to the local container,
    # even if用户在终端里提前导出了 MCP_GATEWAY_ADDRESS（避免连到错误的地址）。
    filesystem_port = os.environ.get("FILESYSTEM_MCP_PORT", "3333")
    os.environ["MCP_GATEWAY_ADDRESS"] = f"http://127.0.0.1:{filesystem_port}"

    # 2. Load LiteTaskSpec from task.yaml
    task_yaml_path = task_dir / "task.yaml"
    spec = LiteTaskSpec.from_yaml(task_yaml_path)

    # 3. Build MCP-Universe ReAct agent with OpenAI LLM
    context = Context()
    mcp_manager = MCPManager(context=context)

    openai_cfg = OpenAIConfig()
    # Use gpt-4o-mini explicitly for this demo task
    openai_cfg.model_name = "gemini-2.5-flash"
    llm = OpenAIModel(config=openai_cfg.to_dict())

    # ReActConfig expects a dict/JSON, not a ReActConfig instance
    react_cfg = {
        "name": "mcpu_mm_demo_react",
        "max_iterations": 20,
    }
    agent = ReAct(mcp_manager=mcp_manager, llm=llm, config=react_cfg)

    # Use the same verbose print callbacks as MCP-Universe benchmark runner
    callbacks = get_vprint_callbacks()

    # 4. Create runner and run the task with the agent
    runner = LiteRunner(text_agent=agent)

    result = await runner.run_task(
        spec=spec,
        task_dir=task_dir,
        callbacks=callbacks,
    )

    print("=== MCPU-MM Demo Result ===")
    print("Answer:")
    print(result["result"])
    print("\nEvaluation results:")
    print(result["evaluation_results"])


def main_sync() -> None:
    """
    Synchronous entrypoint that runs the async main() without using asyncio.run().
    This is to test whether the asyncio.run shutdown behavior is related to
    the anyio/mcp SSE issues.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    finally:
        loop.close()


if __name__ == "__main__":
    main_sync()


