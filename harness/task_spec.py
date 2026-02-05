from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class ModalInputs(BaseModel):
    """
    Describes multimodal inputs for a task (paths are relative to the task directory).
    """

    images: List[str] = Field(default_factory=list, description="Image file paths")
    videos: List[str] = Field(default_factory=list, description="Video file paths")
    pdfs: List[str] = Field(default_factory=list, description="PDF file paths")


class OracleConfig(BaseModel):
    """
    Configuration for oracle solution of a task.
    """

    path: str = Field(
        ...,
        description="Relative path to oracle solution entry (e.g. 'solution.py')",
    )
    kind: str = Field(
        default="python",
        description="Type of oracle solution: 'shell' | 'python' | custom",
    )
    timeout_sec: int = Field(
        default=600,
        description="Maximum time in seconds allowed to run the oracle solution",
    )


class MCPServerConfig(BaseModel):
    """
    Configuration for an MCP server required by the task.
    """

    name: str = Field(..., description="MCP server name (e.g. 'filesystem', 'media_tools')")
    # 可以扩展其他字段，如 version、env 等


class LiteTaskSpec(BaseModel):
    """
    Unified task specification for MCPU-MM.
    
    这是一个统一的任务配置格式，包含：
      - 任务元信息（name, category）
      - 任务描述（question, output_format）
      - MCP server 配置（mcp_servers）
      - 多模态输入（inputs）
      - Oracle solution 配置（oracle，可选）
    """

    name: str = Field(default="", description="Human-readable task name")
    category: str = Field(default="", description="Task category (e.g. 'image_classification')")

    # 任务描述
    question: str = Field(
        default="",
        description="The main question/instruction for the agent",
    )
    output_format: Dict[str, Any] = Field(
        default_factory=dict,
        description="Expected output format (empty dict means free-form)",
    )

    # MCP servers
    mcp_servers: List[MCPServerConfig] = Field(
        default_factory=list,
        description="List of MCP servers required for this task",
    )

    # 多模态输入
    inputs: ModalInputs = Field(
        default_factory=ModalInputs,
        description="Multimodal inputs for this task",
    )

    # Oracle solution 配置（可选）
    oracle: Optional[OracleConfig] = Field(
        default=None,
        description="Oracle solution configuration (optional)",
    )

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "LiteTaskSpec":
        """Load task spec from a YAML file."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Handle nested 'inputs' -> ModalInputs conversion
        if "inputs" in data and isinstance(data["inputs"], dict):
            data["inputs"] = ModalInputs(**data["inputs"])
        
        # Handle 'mcp_servers' -> List[MCPServerConfig]
        if "mcp_servers" in data:
            data["mcp_servers"] = [
                MCPServerConfig(**s) if isinstance(s, dict) else s
                for s in data["mcp_servers"]
            ]
        
        # Handle 'oracle' -> OracleConfig
        if "oracle" in data and isinstance(data["oracle"], dict):
            data["oracle"] = OracleConfig(**data["oracle"])
        
        return cls(**data)

    def get_server_names(self) -> List[str]:
        """Return list of MCP server names required by this task."""
        return [s.name for s in self.mcp_servers]
