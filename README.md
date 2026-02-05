## MCPU-MM

一个轻量级 harness，目前的目标：

- **环境分离**：每个 task 在独立 Docker 环境中执行
- **模块复用**：agent配置、server sse bridge等模块复用 `mcpuniverse`

### 当前项目结构

```text
MCPU-MM/
  README.md
  pyproject.toml          # 轻量依赖声明
  .env                    # 环境变量配置（端口等）
  run_demo_mm.py          # 单任务测试入口
  harness/
    __init__.py
    task_spec.py          # LiteTaskSpec：从 task.yaml 加载任务配置
    task_env.py           # TaskEnv：Docker 环境管理（compose up/stop）
    runner.py             # LiteRunner：调度 Task + Agent + Env + evaluate
    mcp_config.py         # 构造 containerized MCP server 配置
  tasks/
    image_filesystem/
      task.yaml           # 统一的任务配置文件
      Dockerfile          # 任务环境镜像
      docker-compose.yaml # 容器定义
      evaluate.py         # 自定义评估逻辑
      solution.py         # 确定性解法，验证任务可解性
      inputs/             # 初始数据
```

---

### task.yaml 格式

每个任务只需要一个 `task.yaml` 文件，包含所有配置：

```yaml
name: image_filesystem
category: image_classification

question: |
  任务描述...

output_format: {}

mcp_servers:
  - name: filesystem
  - name: media_tools

inputs:
  images:
    - inputs/filesystem_sample.zip
  videos: []
  pdfs: []

# oracle:
#   path: solution.py
#   kind: python
```

---

## Quick Start

### 1. 环境准备

- **Python**: 3.10+
- **Docker**: 已安装并可用
- **MCP-Universe**: 注意需要fork的这个分支[mcpu_mm_new](https://github.com/viczxchen/MCP-Universe/tree/mcpu_mm_new)，包含multimodal agent设定和需要用到的新的自定义mcp server

```bash
cd MCP-Universe
pip install -e .

cd ../MCPU-MM
pip install -e .
```

在 `MCPU-MM/` 根目录下创建 `.env`：

```bash
FILESYSTEM_MCP_PORT=3333
MEDIA_TOOLS_MCP_PORT=4444
```

目前API key直接使用MCP-Universe里的设置

### 2. 运行单个示例任务

**Run Agent Task Soloving**

```bash
cd MCPU-MM
python run_demo_mm.py
```
注意目前multimodal agent只支持react和openai，其余的待开发ing

**Run Solution**

```bash
cd MCPU-MM
python tasks/image_filesystem/solution.py
```
预期：终端输出 `Passed: True`。

