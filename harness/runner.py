from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, List, Set
import sys
from urllib.parse import unquote, urlparse

from mcpuniverse.agent.base import BaseAgent
from mcpuniverse.common.context import Context
from mcpuniverse.tracer import Tracer
from mcpuniverse.tracer.collectors import MemoryCollector
from mcpuniverse.callbacks.base import (
    BaseCallback,
    CallbackMessage,
    MessageType,
    send_message_async,
)

from .task_env import TaskEnv
from .task_spec import LiteTaskSpec


class LiteRunner:
    """
    Minimal runner for a single task with environment isolation.

    It reuses an existing MCP-Universe `BaseAgent` (e.g. ReAct) and runs each
    task inside its own Docker environment.
    """

    def __init__(
        self,
        text_agent: Optional[BaseAgent] = None,
    ):
        self._agent = text_agent

    # ------------------------------------------------------------------ #
    # Private helper methods
    # ------------------------------------------------------------------ #

    def _build_runtime_prompt_suffix(self, spec: LiteTaskSpec, requested_servers: set[str]) -> str:
        """Add execution-time guardrails for unstable tool patterns.

        Temporary test-stage workaround: this prompt suffix is used to reduce
        flaky timeouts in online video runs (especially Playwright tool calls).
        It should be treated as a stopgap patch and can be relaxed/reworked
        once timeout handling is fixed at the tool/runtime level.
        """
        is_online_video = spec.category.startswith("online_video")
        has_video_stack = {"playwright", "youtube-toolbox"}.issubset(requested_servers)
        if not (is_online_video or has_video_stack):
            return ""

        return (
            "\n\nExecution constraints (must follow):\n"
            "- Do NOT call browser_install.\n"
            "- Do NOT use browser_run_code for long waits.\n"
            "- Never call waitForTimeout >= 10000 ms in browser_run_code.\n"
            "- Prefer browser_wait_for / browser_snapshot / browser_take_screenshot over custom sleep loops.\n"
            "- If you need to seek video time, set currentTime quickly and return immediately.\n"
            "- Keep each browser_run_code call short (<8 seconds).\n"
        )

    def _rewrite_file_urls_for_playwright_pdf_http(
        self, question: str, requested_servers: Set[str]
    ) -> str:
        """Rewrite Playwright-oriented ``file://`` URLs to internal HTTP URLs.

        Playwright MCP blocks ``file://``. Task compose serves PDFs from ``/shared`` via
        ``http://<service>:<port>/<basename>`` inside the Docker network. Authors can write
        ``file:///workspace/foo.pdf`` (or ``file:///shared/foo.pdf``) in ``task.yaml``; when
        ``playwright`` is among requested servers, expand to the stable in-network URL so
        ``task.yaml`` does not hardcode ``http://task-env:18080/...``.

        Override host/port with ``MCPU_MM_PDF_HTTP_HOST`` / ``MCPU_MM_PDF_HTTP_INTERNAL_PORT``
        (defaults: ``task-env``, ``18080``). Host-side ``PDF_HTTP_PORT`` only remaps the
        published port; inside the stack the listener stays on ``18080`` unless you change
        compose and the env var together.
        """
        if "playwright" not in requested_servers:
            return question

        import os
        import logging

        logger = logging.getLogger(self.__class__.__name__)
        host = os.getenv("MCPU_MM_PDF_HTTP_HOST", "task-env")
        port = os.getenv("MCPU_MM_PDF_HTTP_INTERNAL_PORT", os.getenv("PDF_HTTP_INTERNAL_PORT", "18080"))

        def substitute(match: re.Match) -> str:
            url = match.group(0)
            try:
                parsed = urlparse(url)
                if parsed.scheme != "file":
                    return url
                path = unquote(parsed.path)
            except Exception:
                return url
            if path.startswith("/workspace/") or path.startswith("/shared/"):
                name = Path(path).name
                if not name:
                    return url
                return f"http://{host}:{port}/{name}"
            return url

        rewritten = re.sub(r"file://[^\s\"'<>]+", substitute, question, flags=re.IGNORECASE)
        if rewritten != question:
            logger.info(
                "Rewrote file:// PDF URLs for Playwright to http://%s:%s/… (see _rewrite_file_urls_for_playwright_pdf_http)",
                host,
                port,
            )
        return rewritten

    async def _run_custom_evaluation(
        self,
        task_dir: Path,
        task_name: str,
        container_name: Optional[str],
        agent_result: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Run custom evaluation if evaluate.py exists in task directory.
        
        Returns:
            List of evaluation results, or None if no custom evaluator exists.
        """
        evaluate_script = task_dir / "evaluate.py"
        if not evaluate_script.exists():
            return None
        
        try:
            import importlib.util
            import sys
            
            # Dynamically import the evaluate module
            spec = importlib.util.spec_from_file_location("task_evaluate", evaluate_script)
            if spec is None or spec.loader is None:
                return None
            
            evaluate_module = importlib.util.module_from_spec(spec)
            sys.modules["task_evaluate"] = evaluate_module
            spec.loader.exec_module(evaluate_module)
            
            # Check if verify function exists
            if not hasattr(evaluate_module, "verify"):
                return None

            # Call verify function
            verify_func = evaluate_module.verify
            import inspect
            verify_sig = inspect.signature(verify_func)
            # Allow evaluators to optionally consume the agent's final answer:
            #   verify(test_dir, container_name, agent_result)
            # Keep backward compatibility with the existing 2-arg form.
            supports_agent_result = len(verify_sig.parameters) >= 3
            if inspect.iscoroutinefunction(verify_func):
                if supports_agent_result:
                    passed, error_msg = await verify_func(task_dir, container_name, agent_result)
                else:
                    passed, error_msg = await verify_func(task_dir, container_name)
            else:
                if supports_agent_result:
                    passed, error_msg = verify_func(task_dir, container_name, agent_result)
                else:
                    passed, error_msg = verify_func(task_dir, container_name)
            
            result = {
                "config": {
                    "func": "custom_evaluate",
                    "op": "",
                    "desc": "Custom evaluation from evaluate.py"
                },
                "response": agent_result,
                "passed": passed,
                "reason": error_msg if not passed else "",
                "error": ""
            }
            return [result]
            
        except Exception as e:
            import logging
            logger = logging.getLogger(self.__class__.__name__)
            logger.warning(f"Custom evaluation failed: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------ #
    # Public APIs
    # ------------------------------------------------------------------ #

    async def run_task(
        self,
        spec: LiteTaskSpec,
        task_dir: Path,
        callbacks: Optional[List[BaseCallback]] = None,
    ) -> Dict[str, Any]:
        """
        Run a task using an existing MCP-Universe BaseAgent.
        """
        if self._agent is None:
            raise RuntimeError("agent is not provided for LiteRunner")

        if callbacks is None:
            callbacks = []

        task_dir = Path(task_dir).resolve()
        task_name = spec.name or task_dir.name

        # Environment (docker-compose is optional)
        env = TaskEnv(
            task_dir=task_dir,
            name=task_name,
            compose_path=task_dir / "docker-compose.yaml",
        )

        trace_collector = MemoryCollector()
        tracer = Tracer(collector=trace_collector)

        import logging
        logger = logging.getLogger(self.__class__.__name__)
        
        with env.spin_up():
            # Get task info directly from spec (no longer need BenchmarkTask)
            question = spec.question
            output_format = spec.output_format
            requested_servers = {cfg.name for cfg in spec.mcp_servers}
            question = self._rewrite_file_urls_for_playwright_pdf_http(question, requested_servers)
            logger.info(f"Task question length: {len(question)} chars")

            # Container name for evaluation
            container_name = env.get_container_name() or f"mcpu-mm-{task_name}"
            logger.info(f"Container name: {container_name}")

            # Get MCP server port mappings
            port_mapping = env.get_mcp_server_ports()
            question = question + self._build_runtime_prompt_suffix(spec, requested_servers)
            
            # Wait for Gateway to be ready (if using containerized servers)
            import asyncio
            import httpx
            from os import getenv
            
            # Fallback to env vars only for servers the task actually requests.
            # Gateway bridges multiple stdio servers on one host port; compose may publish it as
            # GOOGLE_SEARCH_MCP_PORT (e.g. pdf scholar tasks, online_video/search_qa) or FILESYSTEM_MCP_PORT.
            def _gateway_stdio_host_port() -> int:
                return int(
                    getenv("GOOGLE_SEARCH_MCP_PORT")
                    or getenv("FILESYSTEM_MCP_PORT")
                    or "3333"
                )

            default_port_env = {
                "filesystem": ("FILESYSTEM_MCP_PORT", "3333"),
                "playwright": ("PLAYWRIGHT_MCP_PORT", "3335"),
                "media_tools": ("MEDIA_TOOLS_MCP_PORT", "4444"),
                "google-search": ("GOOGLE_SEARCH_MCP_PORT", "3333"),
                "pdf-reader-mcp": ("FILESYSTEM_MCP_PORT", "3333"),
                "arxiv-mcp-server": ("FILESYSTEM_MCP_PORT", "3333"),
                "youtube-toolbox": ("YOUTUBE_TOOLBOX_MCP_PORT", "3336"),
                "serper": ("SERPER_MCP_PORT", "3337"),
                "video-editing": ("VIDEO_EDITING_MCP_PORT", "4455"),
            }
            for server_name in requested_servers:
                if server_name in port_mapping:
                    continue
                if server_name in {"pdf-reader-mcp", "arxiv-mcp-server"}:
                    port_mapping[server_name] = _gateway_stdio_host_port()
                    continue
                if server_name in default_port_env:
                    env_key, default_val = default_port_env[server_name]
                    port_mapping[server_name] = int(getenv(env_key, default_val))

            gateway_backed_servers = {
                "filesystem",
                "google-search",
                "pdf-reader-mcp",
                "arxiv-mcp-server",
            }
            for server_name in sorted(requested_servers & gateway_backed_servers):
                if server_name not in port_mapping:
                    continue
                gateway_port = port_mapping[server_name]
                gateway_url = f"http://127.0.0.1:{gateway_port}/{server_name}/sse"
                logger.info(f"Waiting for Gateway endpoint to be ready at {gateway_url}")

                max_retries = 30
                for i in range(max_retries):
                    try:
                        async with httpx.AsyncClient(timeout=3.0) as client:
                            async with client.stream("GET", gateway_url) as response:
                                if response.status_code == 200:
                                    logger.info(
                                        "Gateway endpoint %s is ready after %s attempts",
                                        server_name,
                                        i + 1,
                                    )
                                    await asyncio.sleep(0.5)
                                    break
                                logger.warning(
                                    "Gateway endpoint %s returned status %s, retrying...",
                                    server_name,
                                    response.status_code,
                                )
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        if i < max_retries - 1:
                            logger.debug(
                                "Gateway endpoint %s health check attempt %s failed: %s, retrying...",
                                server_name,
                                i + 1,
                                e,
                            )
                            await asyncio.sleep(0.5)
                        else:
                            logger.warning(
                                "Gateway endpoint %s health check failed after %s retries: %s",
                                server_name,
                                max_retries,
                                e,
                            )

            async def _wait_for_sse_server(server_name: str, url: str, max_retries: int = 30) -> None:
                """Wait until a native SSE MCP endpoint responds with HTTP 200."""
                logger.info(f"Waiting for {server_name} SSE to be ready at {url}")
                for i in range(max_retries):
                    try:
                        async with httpx.AsyncClient(timeout=3.0) as client:
                            async with client.stream("GET", url) as response:
                                if response.status_code == 200:
                                    logger.info(f"{server_name} SSE is ready after {i+1} attempts")
                                    await asyncio.sleep(0.5)
                                    return
                                logger.warning(
                                    f"{server_name} SSE returned status {response.status_code}, retrying..."
                                )
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        if i < max_retries - 1:
                            logger.debug(
                                f"{server_name} SSE health check attempt {i+1} failed: {e}, retrying..."
                            )
                            await asyncio.sleep(0.5)
                        else:
                            logger.warning(
                                f"{server_name} SSE health check failed after {max_retries} retries: {e}"
                            )

            if "playwright" in requested_servers and "playwright" in port_mapping:
                await _wait_for_sse_server(
                    "playwright",
                    f"http://127.0.0.1:{port_mapping['playwright']}/sse",
                )

            if "media_tools" in requested_servers and "media_tools" in port_mapping:
                await _wait_for_sse_server(
                    "media_tools",
                    f"http://127.0.0.1:{port_mapping['media_tools']}/sse",
                )

            if "youtube-toolbox" in requested_servers and "youtube-toolbox" in port_mapping:
                await _wait_for_sse_server(
                    "youtube-toolbox",
                    f"http://127.0.0.1:{port_mapping['youtube-toolbox']}/sse",
                )

            if "serper" in requested_servers and "serper" in port_mapping:
                await _wait_for_sse_server(
                    "serper",
                    f"http://127.0.0.1:{port_mapping['serper']}/sse",
                )

            if "video-editing" in requested_servers and "video-editing" in port_mapping:
                await _wait_for_sse_server(
                    "video-editing",
                    f"http://127.0.0.1:{port_mapping['video-editing']}/sse",
                )

            # Get volume mappings for path translation (container -> host)
            volume_mappings = env.get_volume_mappings()

            # Map container /workspace -> host dir for file:// -> data URI (OpenAI path normalization).
            # Prefer shared_workspace when present (runtime outputs + seeds copied at container start).
            if "/workspace" not in volume_mappings:
                for candidate in ("shared_workspace", "inputs"):
                    host_workspace = task_dir / candidate
                    if host_workspace.exists():
                        volume_mappings["/workspace"] = str(host_workspace.resolve())
                        break
            
            # Build MCP server configs for containerized servers
            mcp_servers_with_transport = []
            for server_cfg in spec.mcp_servers:
                server_name = server_cfg.name
                transport = "sse" if server_name in port_mapping else "stdio"
                
                server_dict = {
                    "name": server_name,
                    "transport": transport,
                }

                # For filesystem, deny direct media reads when media_tools is present so the
                # agent uses media_tools (read_image/watch_video) for vision; all MCPU-MM
                # tasks are expected to list media_tools.
                if server_name == "filesystem" and "media_tools" in requested_servers:
                    server_dict["permissions"] = [
                        {"tool": "read_media_file", "action": "reject", "arguments": {}},
                        {"tool": "read_multiple_files", "action": "reject", "arguments": {}},
                    ]

                # For stdio python servers, run with the current interpreter so
                # venv-installed modules (e.g. mcpuniverse) are always available.
                if transport == "stdio" and self._agent._mcp_manager:
                    conf = self._agent._mcp_manager._server_configs.get(server_name)
                    if conf and conf.stdio and conf.stdio.command in ("python", "python3"):
                        conf.stdio.command = sys.executable

                mcp_servers_with_transport.append(server_dict)

            # Update MCPManager with SSE addresses for containerized servers
            if self._agent._mcp_manager:
                from mcpuniverse.mcp.config import ServerConfig
                for server_cfg in spec.mcp_servers:
                    server_name = server_cfg.name
                    if server_name in port_mapping:
                        port = port_mapping[server_name]
                        # For native SSE servers, set direct sse_address.
                        if server_name in gateway_backed_servers:
                            continue
                        sse_address = f"http://127.0.0.1:{port}/sse"
                        existing_config = self._agent._mcp_manager._server_configs.get(server_name)
                        if existing_config:
                            existing_config.sse_address = sse_address
                        else:
                            new_config = ServerConfig(sse_address=sse_address)
                            self._agent._mcp_manager._server_configs[server_name] = new_config
            
            # Set container path mapping in agent's context
            if volume_mappings:
                agent_context = Context()
                agent_context.metadata["container_path_mapping"] = volume_mappings
                self._agent.set_context(agent_context)

            # Initialize agent with MCP servers
            logger.info(f"Initializing agent with MCP servers: {[s['name'] for s in mcp_servers_with_transport]}")
            await self._agent.initialize(mcp_servers=mcp_servers_with_transport)
            logger.info("Agent initialized successfully")

            # Send task description to callbacks
            await send_message_async(
                callbacks,
                message=CallbackMessage(
                    source=__file__,
                    type=MessageType.LOG,
                    metadata={"event": "task_description", "data": {"name": task_name, "question": question}},
                ),
            )

            logger.info("Starting agent execution...")
            self._agent.reset()
            response = await self._agent.execute(
                question,
                output_format=output_format,
                tracer=tracer,
                callbacks=callbacks,
            )
            logger.info("Agent execution completed")
            result = response.get_response_str()

            # Run custom evaluation
            evaluation_results = await self._run_custom_evaluation(
                task_dir=task_dir,
                task_name=task_name,
                container_name=container_name,
                agent_result=result,
            )
            
            # If no custom evaluation, return empty list
            if evaluation_results is None:
                evaluation_results = []
            
            trace_records = trace_collector.get(tracer.trace_id)

        return {
            "result": result,
            "evaluation_results": evaluation_results,
            "trace": trace_records,
        }
