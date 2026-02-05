FROM python:3.11-slim

# 我们在镜像中保留一份“种子环境”(/seed)，每次容器启动时都会
# 从 /seed 复制到 /workspace，保证 /workspace 每次都是初始状态。
WORKDIR /

# Install system dependencies for file operations and image processing
# Also install Node.js and pre-install @modelcontextprotocol/server-filesystem
RUN apt-get update && apt-get install -y \
    git \
    unzip \
    file \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @modelcontextprotocol/server-filesystem \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
# These versions match the MCP-Universe venv to avoid compatibility issues
COPY requirements-mcpuniverse.txt /tmp/requirements-mcpuniverse.txt
RUN pip install --no-cache-dir -r /tmp/requirements-mcpuniverse.txt && \
    # Patch fastmcp Tool.from_function to avoid issubclass() on non-class annotations
    python - << 'PY'
from pathlib import Path
path = Path("/usr/local/lib/python3.11/site-packages/mcp/server/fastmcp/tools/base.py")
text = path.read_text(encoding="utf-8")
old = """        if context_kwarg is None:
            sig = inspect.signature(fn)
            for param_name, param in sig.parameters.items():
                if get_origin(param.annotation) is not None:
                    continue
                if issubclass(param.annotation, Context):
                    context_kwarg = param_name
                    break
"""
new = """        if context_kwarg is None:
            sig = inspect.signature(fn)
            for param_name, param in sig.parameters.items():
                # Skip generic/typing annotations (e.g. list[str], Annotated[…])
                if get_origin(param.annotation) is not None:
                    continue
                ann = param.annotation
                # Some functions may have missing annotations or special typing objects
                # (e.g. inspect._empty, typing.Any). These are not valid for issubclass.
                if not isinstance(ann, type):
                    continue
                if issubclass(ann, Context):
                    context_kwarg = param_name
                    break
"""
if old in text:
    path.write_text(text.replace(old, new), encoding="utf-8")
PY

# 将 inputs 的内容复制到只读种子目录 /seed
COPY inputs/. /seed/

# 初始化一次 workspace，后续每次容器启动时会在 entrypoint 中重置
RUN mkdir -p /workspace && cp -r /seed/. /workspace/

# 默认工作目录设为 /workspace，方便交互
WORKDIR /workspace
