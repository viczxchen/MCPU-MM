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
    offline_image/
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
  - name: media_tools   # required for all tasks: vision via read_image/watch_video

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
python tasks/offline_image/image_filesystem/solution.py
```
预期：终端输出 `Passed: True`。

### 3. YouTube 登录态导出（本机）并给容器复用（for tasks involving youtube browsing）

> 目的：在本机手动登录一次 YouTube，导出 `storage_state`，后续在 Docker/容器里复用，避免反复登录。

#### 3.1 安装 Playwright（仅首次）

```bash
cd MCPU-MM
pip install playwright
python -m playwright install chromium
```

#### 3.2 本机手动登录并导出 `storage_state`（自动验证）

```bash
cd MCPU-MM
python scripts/youtube_auth.py export
```

执行后会弹出 Chromium，你手动完成 Google/YouTube 登录，回到终端按回车，脚本会：
1. 保存登录态到 `playwright/.auth/youtube.json`
2. **自动验证** 登录态是否有效

若看到 `✓ 登录态导出成功且验证通过！` 即表示可用。

#### 3.3 验证已有登录态

如果之前导出过，想检查是否还有效：

```bash
cd MCPU-MM
python scripts/youtube_auth.py verify
```

#### 3.4 给容器复用

docker-compose 已配置好自动挂载 `playwright/.auth` 到 `/auth`，容器内直接使用：

```python
context = browser.new_context(storage_state="/auth/youtube.json")
```

手动测试容器内登录态：

```bash
cd MCPU-MM/tasks/online_video/sports
docker-compose run --rm playwright-mcp sh
# 进入容器后
python3 /mcpu-mm/scripts/youtube_auth.py use --state-path /auth/youtube.json --verify
```

#### 3.5 安全注意事项

- `storage_state` 包含敏感 cookie/token，**不要提交到 git**。
- `playwright/.auth/` 已添加到 `.gitignore`。

## TODO


1. task容器化迁移 + 测试所有种类的task: 排除所有非agent能力导致的bug
2. 难度定级: 初步难度详细描述solution + gpt-4o可以完成，后续把指示模糊增加难度
3. 数据生成：
  - 现成benchmark的迁移
  - 生成+找data source(自动化)

**长期架构问题**
- multimodal llm, agent workflow 适配（目前只改了openai+react）
- 并行架构（目录映射逻辑需要改动）



