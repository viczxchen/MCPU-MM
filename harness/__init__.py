"""
MCPU-MM harness package.

This package provides:
  - TaskEnv: per-task Docker environment isolation
  - LiteTaskSpec: description of a single benchmark task (including MCP config, multimodal inputs, oracle)
  - MultiModalAgent: API-level multimodal agent (only used in this lite harness)
  - LiteRunner: high-level runner to execute a single task with environment isolation
"""

from .task_spec import LiteTaskSpec, OracleConfig, ModalInputs  # noqa: F401
from .task_env import TaskEnv  # noqa: F401
from .runner import LiteRunner  # noqa: F401


