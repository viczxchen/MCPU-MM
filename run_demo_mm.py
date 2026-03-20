"""
Run a single demo task using MCP-Universe ReAct agent inside an isolated Docker env.

Usage (from the MCPU-MM directory, with MCP-Universe installed in the env):

    python -m MCPU_MM.run_demo_mm
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from mcpuniverse.agent.react import ReAct
from mcpuniverse.common.context import Context
from mcpuniverse.llm.openai import OpenAIModel, OpenAIConfig
from mcpuniverse.mcp.manager import MCPManager
from mcpuniverse.callbacks.handlers.vprint import get_vprint_callbacks

from harness import LiteRunner, LiteTaskSpec


DEFAULT_DEMO_TASK_NAME = "web_understanding"
DEFAULT_LOG_DIR = "logs/run_demo_mm"


class _TeeStream:
    """Write terminal output to both console and a log file."""

    def __init__(self, console_stream, file_stream):
        self._console_stream = console_stream
        self._file_stream = file_stream

    def write(self, data):
        self._console_stream.write(data)
        self._file_stream.write(data)
        return len(data)

    def flush(self):
        self._console_stream.flush()
        self._file_stream.flush()


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
        # Keep existing behavior for most variables, but force OPENAI_* from .env
        # to avoid stale shell exports overriding model/base_url/api_key unexpectedly.
        if key.startswith("OPENAI_"):
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def _resolve_demo_task_name(cli_task: str | None = None) -> str:
    """Resolve task name with precedence: --task > env > default."""
    if cli_task:
        return cli_task
    return os.environ.get("MCPU_MM_DEMO_TASK", DEFAULT_DEMO_TASK_NAME)


def _get_demo_task_dir(project_root: Path, task_name: str) -> Path:
    tasks_root = project_root / "tasks"

    # Support explicit relative path under tasks/, e.g. "offline_image/web_understanding".
    explicit = tasks_root / task_name
    if (explicit / "task.yaml").exists():
        return explicit

    # Otherwise, resolve by directory name from any depth under tasks/.
    all_task_dirs = [p.parent for p in tasks_root.rglob("task.yaml")]
    matches = [p for p in all_task_dirs if p.name == task_name]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        rel_matches = sorted(str(p.relative_to(tasks_root)) for p in matches)
        raise ValueError(
            f"Ambiguous task name '{task_name}'. Use an explicit path under tasks/, "
            f"for example '--task {rel_matches[0]}'. Candidates: {rel_matches}"
        )

    rel_all = sorted(str(p.relative_to(tasks_root)) for p in all_task_dirs)
    raise FileNotFoundError(
        f"Task '{task_name}' not found under {tasks_root}. "
        f"Available tasks: {rel_all}"
    )


def _best_effort_stop_task_env(task_dir: Path, task_name: str) -> None:
    """Try to stop compose services even when run is interrupted by Ctrl+C."""
    compose_file = task_dir / "docker-compose.yaml"
    if not compose_file.exists():
        return
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-p",
        task_name,
        "stop",
    ]
    subprocess.run(cmd, cwd=str(task_dir), capture_output=True, text=True, check=False)


def _ensure_local_no_proxy() -> None:
    """Prevent localhost MCP traffic from going through HTTP proxies."""
    required = ["127.0.0.1", "localhost"]
    for key in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(key, "")
        parts = [p.strip() for p in existing.split(",") if p.strip()]
        changed = False
        for item in required:
            if item not in parts:
                parts.append(item)
                changed = True
        if changed or not existing:
            os.environ[key] = ",".join(parts)


def _enable_terminal_log(project_root: Path, task_name: str, log_dir: str) -> tuple[Path, object, object, object]:
    logs_dir = project_root / log_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    safe_task_name = task_name.replace("/", "__")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"{ts}_{safe_task_name}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _TeeStream(original_stdout, log_file)
    sys.stderr = _TeeStream(original_stderr, log_file)
    return log_path, original_stdout, original_stderr, log_file


async def main(task_name: str) -> None:
    # Set up logging to show verbose output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(process)d %(name)s %(levelname)s [%(funcName)s():%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S,%f",
    )
    
    # 1. Locate demo task directory
    project_root = Path(__file__).resolve().parent
    task_dir = _get_demo_task_dir(project_root, task_name)

    # Load environment variables from .env at project root (if present)
    _load_env_file(project_root / ".env")

    # For this local demo, ALWAYS force Gateway to point to the local container,
    # even if用户在终端里提前导出了 MCP_GATEWAY_ADDRESS（避免连到错误的地址）。
    # Prefer GOOGLE_SEARCH_MCP_PORT when set (same mapping as online_video/search_qa & pdf scholar tasks),
    # else FILESYSTEM_MCP_PORT (gateway-backed stdio servers share this host port by default).
    gateway_port = (
        os.environ.get("GOOGLE_SEARCH_MCP_PORT")
        or os.environ.get("FILESYSTEM_MCP_PORT")
        or "3333"
    )
    os.environ["MCP_GATEWAY_ADDRESS"] = f"http://127.0.0.1:{gateway_port}"
    _ensure_local_no_proxy()

    # 2. Load LiteTaskSpec from task.yaml
    task_yaml_path = task_dir / "task.yaml"
    spec = LiteTaskSpec.from_yaml(task_yaml_path)

    # 3. Build MCP-Universe ReAct agent with OpenAI LLM
    context = Context()
    mcp_manager = MCPManager(context=context)

    openai_cfg = OpenAIConfig()
    # Allow selecting model via .env (OPENAI_MODEL), fallback keeps previous behavior.
    openai_cfg.model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")
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
    parser = argparse.ArgumentParser(description="Run a single MCPU-MM demo task.")
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help=(
            "Task directory name or relative path under tasks/ "
            "(e.g. web_understanding or offline_image/web_understanding)."
        ),
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=DEFAULT_LOG_DIR,
        help="Directory to store terminal output logs for each run.",
    )
    args = parser.parse_args()
    task_name = _resolve_demo_task_name(args.task)

    loop = asyncio.new_event_loop()
    project_root = Path(__file__).resolve().parent
    task_dir = _get_demo_task_dir(project_root, task_name)
    log_path, original_stdout, original_stderr, log_file = _enable_terminal_log(
        project_root=project_root,
        task_name=task_name,
        log_dir=args.log_dir,
    )
    print(f"[run_demo_mm] Logging terminal output to: {log_path}")
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main(task_name))
    except KeyboardInterrupt:
        logging.warning("Interrupted by user (Ctrl+C). Cleaning up task environment...")
    finally:
        _best_effort_stop_task_env(task_dir, task_name)
        loop.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        log_file.close()
        print(f"[run_demo_mm] Log saved: {log_path}")


if __name__ == "__main__":
    main_sync()


