# DeepMedical后端文档

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 目录

- [DeepMedical后端文档](#deepmedical后端文档)
  - [目录](#目录)
  - [快速开始](#快速开始)
  - [安装设置](#安装设置)
    - [配置](#配置)
  - [使用方法](#使用方法)
    - [基本执行](#基本执行)
    - [API 服务器](#api-服务器)
    - [高级配置](#高级配置)
    - [智能体提示系统](#智能体提示系统)
      - [核心智能体角色](#核心智能体角色)
      - [提示系统架构](#提示系统架构)
  - [Docker](#docker)
  - [网页界面](#网页界面)
  - [Docker Compose (包括前后端)](#docker-compose-包括前后端)

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/SDU-Gary/DeepMedical.git
cd DeepMedical

cd DM-crawler

# 安装依赖
pip install poetry  # 或者 pip install pdm
poetry install      # 或者 pdm install

# Playwright install to use Chromium for browser-use by default
playwright install

# 配置环境
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥

# 运行项目
python main.py

```

这将允许你在Terminal上运行项目。

## 安装设置

### 配置

您可以在项目根目录创建 .env 文件并配置以下环境变量，您可以复制 .env.example 文件作为模板开始：

```bash
cp .env.example .env
```

```ini
# 工具 API 密钥
TAVILY_API_KEY=your_tavily_api_key
JINA_API_KEY=your_jina_api_key  # 可选

# 浏览器配置
CHROME_INSTANCE_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome  # 可选，Chrome 可执行文件路径
CHROME_HEADLESS=False  # 可选，默认是 False
CHROME_PROXY_SERVER=http://127.0.0.1:10809  # 可选，默认是 None
CHROME_PROXY_USERNAME=  # 可选，默认是 None
CHROME_PROXY_PASSWORD=  # 可选，默认是 None
```

## 使用方法

### 基本执行

使用默认设置运行 DeepMedical：

```bash
python main.py
```

### API 服务器

DeepMedical 提供基于 FastAPI 的 API 服务器，支持流式响应：

```bash
# 启动 API 服务器
make serve

# 或直接运行
python server.py
```

API 服务器提供以下端点：

- `POST /api/chat/stream`：用于 LangGraph 调用的聊天端点，流式响应
  - 请求体：

  ```json
  {
    "messages": [{ "role": "user", "content": "在此输入您的查询" }],
    "debug": false
  }
  ```

  - 返回包含智能体响应的服务器发送事件（SSE）流

### 高级配置

DeepMedical 可以通过 `src/config` 目录中的各种配置文件进行自定义：

- `env.py`：配置 LLM 模型、API 密钥和基础 URL
- `tools.py`：调整工具特定设置（如 Tavily 搜索结果限制）
- `agents.py`：修改团队组成和智能体系统提示

### 智能体提示系统

DeepMedical 在 `src/prompts` 目录中使用复杂的提示系统来定义智能体的行为和职责：

#### 核心智能体角色

- **主管（[`src/prompts/supervisor.md`](src/prompts/supervisor.md)）**：通过分析请求并确定由哪个专家处理来协调团队并分配任务。负责决定任务完成情况和工作流转换。

- **研究员（[`src/prompts/researcher.md`](src/prompts/researcher.md)）**：专门通过网络搜索和数据收集来收集信息。使用 Tavily 搜索和网络爬取功能，避免数学计算或文件操作。

- **程序员（[`src/prompts/coder.md`](src/prompts/coder.md)）**：专业软件工程师角色，专注于 Python 和 bash 脚本。处理：
  - Python 代码执行和分析
  - Shell 命令执行
  - 技术问题解决和实现

- **文件管理员（[`src/prompts/file_manager.md`](src/prompts/file_manager.md)）**：处理所有文件系统操作，重点是正确格式化和保存 markdown 格式的内容。

- **浏览器（[`src/prompts/browser.md`](src/prompts/browser.md)）**：网络交互专家，处理：
  - 网站导航
  - 页面交互（点击、输入、滚动）
  - 从网页提取内容

#### 提示系统架构

提示系统使用模板引擎（[`src/prompts/template.py`](src/prompts/template.py)）来：

- 加载特定角色的 markdown 模板
- 处理变量替换（如当前时间、团队成员信息）
- 为每个智能体格式化系统提示

每个智能体的提示都在单独的 markdown 文件中定义，这样无需更改底层代码就可以轻松修改行为和职责。

## Docker

DeepMedical 可以运行在 Docker 容器中。默认情况下，API 服务器在端口 8000 上运行。

```bash
docker build -t deepmedical .
docker run --name deepmedical -d --env-file .env -e CHROME_HEADLESS=True -p 8000:8000 deepmedical
```

你也可以直接用 Docker 运行 CLI：

```bash
docker build -t deepmedical .
docker run --rm -it --env-file .env -e CHROME_HEADLESS=True deepmedical uv run python main.py
```

## 网页界面

DeepMedical 提供一个不算好看的网页界面。

请参考 [DeepMedical-web](README-web.md) 项目了解更多信息。

## Docker Compose (包括前后端)

DeepMedical 提供了 docker-compose 设置，可以轻松地同时运行后端和前端：

```bash
# 启动后端和前端
docker-compose up -d

# 后端将在 http://localhost:8000 可用
# 前端将在 http://localhost:3000 可用，可以通过浏览器访问
```

这将：

1. 构建并启动 DeepMedical 后端容器
2. 构建并启动 DeepMedical Web UI 容器
3. 使用共享网络连接它们

在启动服务之前，请确保已准备好包含必要 API 密钥的 `.env` 文件。
