FROM python:3.11-slim

WORKDIR /

RUN apt-get update && apt-get install -y \
    git \
    unzip \
    file \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @modelcontextprotocol/server-filesystem \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-mcpuniverse.txt /tmp/requirements-mcpuniverse.txt
RUN pip install --no-cache-dir -r /tmp/requirements-mcpuniverse.txt && \
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
                if get_origin(param.annotation) is not None:
                    continue
                ann = param.annotation
                if not isinstance(ann, type):
                    continue
                if issubclass(ann, Context):
                    context_kwarg = param_name
                    break
"""
if old in text:
    path.write_text(text.replace(old, new), encoding="utf-8")
PY

COPY inputs/. /seed/
RUN mkdir -p /workspace && cp -r /seed/. /workspace/

WORKDIR /workspace
