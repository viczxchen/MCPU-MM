"""
MCPU-MM top-level package.

This package provides a minimal multimodal evaluation harness that
reuses MCP-Universe's Task / Evaluator logic while adding:

- Per-task Docker environment isolation
- A lightweight multimodal agent interface (API-level vision)
- Simple runners for single-task experiments
"""

from .harness import (  # noqa: F401
    LiteRunner,
    MultiModalAgent,
    MultiModalResponse,
    TaskEnv,
    LiteTaskSpec,
    ModalInputs,
    OracleConfig,
)


