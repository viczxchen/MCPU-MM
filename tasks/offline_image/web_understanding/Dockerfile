FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /workspace

COPY requirements-mcpuniverse.txt /tmp/requirements-mcpuniverse.txt
RUN pip install --no-cache-dir -r /tmp/requirements-mcpuniverse.txt && \
    python - << 'PY'
from pathlib import Path

candidates = sorted(Path("/usr/local/lib").rglob("mcp/server/fastmcp/tools/base.py"))
if not candidates:
    raise SystemExit("fastmcp base.py not found for patching")

path = candidates[0]
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

# Serve the offline HTML snapshot to the Playwright MCP client.
COPY inputs/. /workspace/

EXPOSE 18080

CMD ["python3", "-m", "http.server", "18080", "--directory", "/workspace"]
