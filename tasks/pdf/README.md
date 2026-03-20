# PDF tasks (migrated from `task分工/5_PDF tasks (40)`)

Sample tasks live under:

| Task | Path under `tasks/pdf/` | Local data |
|------|-------------------------|------------|
| Paper search | `scholar_search/paper_search/` | No bundled PDF (search-only sample) |
| Citation verification | `scholar_search/citation_verification/` | `inputs/citation_sample.pdf` |
| Chart comprehension | `pdf_understanding/chart_comprehension/` | `inputs/chart_sample.pdf` |
| Content verification | `pdf_understanding/content_verification/` | `inputs/Sample_Auto_Arena.pdf` |

## Stack

- **Gateway (stdio → SSE):** `google-search` / `pdf-reader-mcp` / `arxiv-mcp-server` as configured in `MCP-Universe/.../server_list.json`.
- **Playwright MCP:** `mcr.microsoft.com/playwright/mcp:latest` sidecar (same pattern as `offline_image/web_understanding`).
- **Node/npm** in the task image: required so `npx` can launch `@modelcontextprotocol/server-pdf` and `papers-mcp`.

### Playwright + PDFs

- The Playwright MCP **blocks raw `file://` in the browser**. Task env serves `/shared` over **`http://0.0.0.0:18080`** inside the container (host mapping: **`PDF_HTTP_PORT`**).
- **Task YAML convention:** write Playwright targets as **`file:///workspace/<file>.pdf`** (or **`file:///shared/...`**). `harness/runner.py` rewrites those to **`http://task-env:<port>/<file>.pdf`** before the agent runs (default in-stack port **18080**). Override with **`MCPU_MM_PDF_HTTP_HOST`** / **`MCPU_MM_PDF_HTTP_INTERNAL_PORT`** if you change compose.
- PDFs are copied into `/shared` at container start so both **pdf-reader** (`/workspace/…`) and **Playwright** can use them.
- `NO_PROXY` includes `task-env` so host proxy settings do not break internal HTTP to the task container.

### pdf-reader-mcp (`@modelcontextprotocol/server-pdf`)

- **Local files:** use paths under the allowed root, e.g. **`/workspace/<file>.pdf`** (matches gateway args in `server_list.json`).
- **Remote URLs:** the upstream server **only allows `https:`** for HTTP(S) fetch. Do **not** pass internal **`http://task-env:…`** URLs to pdf-reader — use **`/workspace/...`** instead. (Playwright uses the rewritten HTTP URL from the section above.)

### Why the first `docker compose build` can feel slow

Compared with tasks like `offline_image/web_understanding` (Playwright Python base + `pip` + copy `inputs/` only), PDF tasks **also**:

1. **Install MCP-Universe Python deps** (`requirements-mcpuniverse.txt`) — same as many other tasks.
2. **Install Node.js** so the gateway can spawn **`npx @modelcontextprotocol/server-pdf`** and **`npx papers-mcp`**.  
   - Older Dockerfiles used Ubuntu’s `apt install nodejs npm`; the **`npm` meta-package pulls hundreds of extra `.deb`s** (tooling unrelated to `npx`), which made builds very slow and sensitive to mirror errors (`502` from `ports.ubuntu.com`).  
   - **Current Dockerfiles use [NodeSource](https://github.com/nodesource/distributions) Node 20** — only `nodejs` (+ bundled `npm`/`npx`), much smaller and faster.
3. **Two services** in compose: `task-env` (build) + `playwright-mcp` (pull `mcr.microsoft.com/playwright/mcp:latest` the first time).

After a successful build, **layers are cached** — later `compose up` is usually quick unless you change the `Dockerfile` or `requirements`.

## Ports & search API

- **Gateway (stdio → SSE)** is exposed on **`GOOGLE_SEARCH_MCP_PORT`** for scholar tasks (same as `online_video/search_qa`), and on **`FILESYSTEM_MCP_PORT`** for pdf-only tasks (`chart_*`, `content_*`). Defaults are both `3333`.
- `run_demo_mm.py` sets `MCP_GATEWAY_ADDRESS` to `GOOGLE_SEARCH_MCP_PORT` if set, otherwise `FILESYSTEM_MCP_PORT` (default `3333`).
- **`google-search`** uses **SerpAPI** and reads **`SERP_API_KEY`** from the environment. Compose also accepts **`SERPER_API_KEY`** as a fallback alias (mapped into `SERP_API_KEY`).

## Proxy

`task-env` and `playwright-mcp` use the same pattern as **`online_video/search_qa`** (YouTube stack): `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` from `MCPU_MM_*` in `.env` (default `host.docker.internal:7890`).

Example:

```bash
cd MCPU-MM
python run_demo_mm.py --task pdf/scholar_search/citation_verification
# or
python run_demo_mm.py --task pdf/pdf_understanding/chart_comprehension
```
