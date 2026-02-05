from __future__ import annotations

import os
import subprocess
import yaml
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Dict

from mcpuniverse.common.logger import get_logger


class TaskEnv:
    """
    Per-task Docker environment with MCP server container support.

    Responsibilities:
      - start an isolated environment for a single task (one container or a compose stack)
      - manage MCP server containers and their port mappings
      - stop and clean it up afterwards

    This is intentionally simpler than Terminal-Bench's DockerComposeManager and only
    serves the MCPU-MM harness.
    """

    def __init__(
        self,
        task_dir: Path,
        name: str,
        compose_path: Optional[Path] = None,
    ):
        self.task_dir = Path(task_dir).resolve()
        self.name = name
        self.compose_path = compose_path
        self._logger = get_logger(self.__class__.__name__)
        self._port_mapping: Dict[str, int] = {}

    @contextmanager
    def spin_up(self) -> Generator["TaskEnv", None, None]:
        """
        Context manager to start and stop the environment.

        Usage:
            env = TaskEnv(...)
            with env.spin_up():
                # run agent + tests here
        """
        self._logger.info("Starting task environment: %s", self.name)
        self.start()
        try:
            yield self
        finally:
            self._logger.info("Stopping task environment: %s", self.name)
            self.stop()

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #

    def start(self) -> None:
        """Start the environment using docker-compose if available, else noop."""
        if self.compose_path and self.compose_path.exists():
            # 这里只负责启动 docker-compose，端口之类通过环境变量配置，
            # 避免在这里去解析 docker-compose.yaml，后续 server 多了会非常繁琐。
            self._start_with_compose()
        else:
            # For now, we only support docker-compose based envs.
            # Later we can add a simple `docker run`-based fallback if needed.
            self._logger.warning(
                "No docker-compose.yaml found for task %s, "
                "skipping container startup (host env only).",
                self.name,
            )

    def stop(self) -> None:
        """Stop the environment."""
        if self.compose_path and self.compose_path.exists():
            self._stop_with_compose()

    # --------------------------------------------------------------------- #
    # Compose helpers
    # --------------------------------------------------------------------- #

    def _start_with_compose(self) -> None:
        compose_file = self.compose_path.resolve()
        env = os.environ.copy()
        env.update(
            {
                "MCPU_MM_TASK_NAME": self.name,
            }
        )
        cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "-p",
            self.name,
            "up",
            "-d",
        ]
        self._logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            cwd=str(self.task_dir),
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self._logger.error("docker compose up failed: %s", result.stderr)
            raise RuntimeError(f"Failed to start task environment: {self.name}")

    def _stop_with_compose(self) -> None:
        compose_file = self.compose_path.resolve()
        cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "-p",
            self.name,
            "stop",
        ]
        self._logger.debug("Running: %s", " ".join(cmd))
        subprocess.run(
            cmd,
            cwd=str(self.task_dir),
            capture_output=True,
            text=True,
        )
        # Clear port mappings after stopping
        self._port_mapping.clear()

    # --------------------------------------------------------------------- #
    # Port mapping and MCP server management
    # ---------------------------------------------------------------------

    def get_mcp_server_ports(self) -> Dict[str, int]:
        """
        Get port mappings for MCP servers.

        Returns:
            Dictionary mapping server names to their host ports.
            e.g., {"filesystem": 3333, "media_tools": 4444}
        目前端口的“真相”完全由环境变量（例如 FILESYSTEM_MCP_PORT / MEDIA_TOOLS_MCP_PORT）
        在上层 `LiteRunner` 中做兜底配置，这里不再尝试解析 docker-compose.yaml，
        以免后续 MCP server 一多，这里的推断逻辑越来越复杂。
        """
        return {}

    def get_volume_mappings(self) -> Dict[str, str]:
        """
        Get volume mappings from docker-compose.yaml.

        Returns:
            Dictionary mapping container paths to host paths.
            e.g., {"/workspace": "/Users/.../task_dir"}
        """
        if not self.compose_path or not self.compose_path.exists():
            return {}

        try:
            with open(self.compose_path, "r", encoding="utf-8") as f:
                compose_data = yaml.safe_load(f)

            volume_mappings = {}
            services = compose_data.get("services", {})
            for service_name, service_config in services.items():
                volumes = service_config.get("volumes", [])
                for volume in volumes:
                    if isinstance(volume, str) and ":" in volume:
                        # Format: "host_path:container_path"
                        parts = volume.split(":", 1)
                        if len(parts) == 2:
                            host_path, container_path = parts
                            # Resolve relative paths
                            if not os.path.isabs(host_path):
                                host_path = str(self.task_dir / host_path)
                            volume_mappings[container_path] = host_path
            return volume_mappings
        except Exception as e:
            self._logger.warning(
                "Failed to extract volume mappings from docker-compose.yaml: %s", e
            )
            return {}

    def get_container_name(self) -> Optional[str]:
        """
        Get the container name from docker-compose.yaml.
        
        Returns:
            Container name if found, None otherwise.
        """
        if not self.compose_path or not self.compose_path.exists():
            return None
        
        try:
            with open(self.compose_path, "r", encoding="utf-8") as f:
                compose_data = yaml.safe_load(f)
            
            services = compose_data.get("services", {})
            for service_name, service_config in services.items():
                container_name = service_config.get("container_name")
                if container_name:
                    # Replace environment variables in container name
                    import re
                    def replace_env(match):
                        var_name = match.group(1)
                        default = match.group(2) if match.group(2) else ""
                        return os.environ.get(var_name, default)
                    
                    container_name = re.sub(
                        r'\$\{([^:}]+)(?::-([^}]*))?\}',
                        replace_env,
                        container_name
                    )
                    return container_name
            return None
        except Exception as e:
            self._logger.warning(
                "Failed to extract container name from docker-compose.yaml: %s", e
            )
            return None


