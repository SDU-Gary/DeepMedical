# API 参考文档

## 目录

- [API 参考文档](#api-参考文档)
  - [目录](#目录)
  - [项目概述](#项目概述)
  - [API 端点](#api-端点)
    - [流式对话](#流式对话)
    - [浏览器历史](#浏览器历史)
    - [团队成员配置](#团队成员配置)
  - [状态与事件](#状态与事件)
  - [工作流程](#工作流程)
    - [图结构](#图结构)
    - [节点说明](#节点说明)
  - [配置](#配置)
    - [环境变量](#环境变量)
    - [模型配置](#模型配置)
    - [团队成员配置](#团队成员配置-1)
  - [错误处理](#错误处理)
  - [后端开发指南](#后端开发指南)
    - [项目架构](#项目架构)
    - [添加新API端点](#添加新api端点)
      - [步骤 1: 定义数据模型](#步骤-1-定义数据模型)
      - [步骤 2: 实现 API 端点](#步骤-2-实现-api-端点)
      - [步骤 3: 添加辅助函数](#步骤-3-添加辅助函数)
    - [与前端协作](#与前端协作)
      - [API 契约定义](#api-契约定义)
      - [API 文档生成](#api-文档生成)
      - [使用 CORS 配置](#使用-cors-配置)
      - [前后端通信模式](#前后端通信模式)
      - [为前端提供示例代码](#为前端提供示例代码)
    - [部署与测试](#部署与测试)
      - [单元测试](#单元测试)
      - [集成测试](#集成测试)
      - [部署检查列表](#部署检查列表)

## 项目概述

本模块是一个基于 LangGraph 的智能代理工作流系统，它将语言模型与专业工具（如网络搜索、网页浏览和代码执行）相结合，能够执行复杂的自动化任务。系统采用多代理协作的方式，每个代理负责特定的任务领域。

主要特点：

- 基于 LangGraph 的工作流引擎
- 多代理协作架构
- 支持多种大语言模型 (LLM)
- 丰富的工具集成（搜索、浏览器、代码执行等）
- 流式响应机制

## API 端点

### 流式对话

**端点**：`POST /api/chat/stream`

**描述**：这是主要的聊天端点，用于处理用户请求并返回流式响应。采用服务器发送事件 (SSE) 机制实现实时反馈。

**请求参数**：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "计算 DeepSeek R1 在 HuggingFace 上的影响力指数"
    }
  ],
  "debug": false,
  "deep_thinking_mode": false,
  "search_before_planning": false,
  "team_members": ["researcher", "coder", "browser", "reporter"]
}
```

| 参数 | 类型 | 说明 |
| ----- | ----- | ----- |
| messages | Array | 对话历史，包含用户和助手的消息 |
| debug | Boolean | 可选，是否启用调试模式，默认为 false |
| deep_thinking_mode | Boolean | 可选，是否启用深度思考模式，默认为 false |
| search_before_planning | Boolean | 可选，是否在规划前先搜索信息，默认为 false |
| team_members | Array | 可选，指定参与工作流的团队成员 |

每条消息的格式如下：

```json
{
  "role": "string",  // "user" 或 "assistant"
  "content": "string" 或 [
    {
      "type": "text",
      "text": "string"
    },
    {
      "type": "image",
      "image_url": "string"
    }
  ]
}
```

**响应**：

响应通过 SSE 流式传输，包含多种事件类型：

| 事件类型 | 说明 |
| ----- | ----- |
| start_of_workflow | 工作流开始 |
| start_of_agent | 代理开始工作 |
| end_of_agent | 代理完成工作 |
| start_of_llm | LLM 开始生成 |
| end_of_llm | LLM 完成生成 |
| message | 消息片段 |
| tool_call | 工具调用 |
| tool_call_result | 工具调用结果 |
| end_of_workflow | 工作流结束 |
| final_session_state | 最终会话状态 |

**示例响应**：

```text
event: start_of_workflow
data: {"workflow_id": "123e4567-e89b-12d3-a456-426614174000", "input": [{...}]}

event: start_of_agent
data: {"agent_name": "planner", "agent_id": "123e4567-e89b-12d3-a456-426614174000_planner_1"}

event: message
data: {"message_id": "msg_1", "delta": {"content": "我将首先分析这个问题..."}}

event: tool_call
data: {"tool_call_id": "123e4567-e89b-12d3-a456-426614174000_researcher_search_1", "tool_name": "search", "tool_input": "DeepSeek R1 HuggingFace 影响力指数"}

event: tool_call_result
data: {"tool_call_id": "123e4567-e89b-12d3-a456-426614174000_researcher_search_1", "tool_name": "search", "tool_result": "搜索结果..."}

event: end_of_workflow
data: {"workflow_id": "123e4567-e89b-12d3-a456-426614174000", "messages": [{...}]}

event: final_session_state
data: {"messages": [{...}]}
```

### 浏览器历史

**端点**：`GET /api/browser_history/{filename}`

**描述**：获取浏览器操作的 GIF 历史记录文件。

**路径参数**：

| 参数 | 类型 | 说明 |
| ----- | ----- | ----- |
| filename | String | GIF 文件名（必须以 .gif 结尾） |

**响应**：

成功时返回 GIF 文件，媒体类型为 `image/gif`。

### 团队成员配置

**端点**：`GET /api/team_members`

**描述**：获取所有团队成员的配置信息。

**响应**：

```json
{
  "team_members": {
    "researcher": {
      "name": "researcher",
      "desc": "负责搜索和收集相关信息，理解用户需求并进行研究分析",
      "desc_for_llm": "使用搜索引擎和网络爬虫从互联网收集信息。输出一份总结发现的 Markdown 报告。研究员不能进行数学计算或编程。",
      "is_optional": false
    },
    "coder": {
      "name": "coder",
      "desc": "负责代码实现、调试和优化，处理技术编程任务",
      "desc_for_llm": "执行 Python 或 Bash 命令，执行数学计算，并输出 Markdown 报告。必须用于所有数学计算。",
      "is_optional": true
    },
    "browser": {
      "name": "browser",
      "desc": "负责网络浏览、内容提取和交互",
      "desc_for_llm": "直接与网页交互，执行复杂的操作和交互。您还可以利用`browser`执行域内搜索，如 Facebook、Instagram、Github 等。",
      "is_optional": true
    },
    "reporter": {
      "name": "reporter",
      "desc": "负责总结分析结果，生成报告并向用户呈现最终成果",
      "desc_for_llm": "基于每个步骤的结果撰写专业报告。",
      "is_optional": false
    }
  }
}
```

## 状态与事件

工作流引擎基于 LangGraph 实现，核心状态定义如下：

```python
class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # 常量
    TEAM_MEMBERS: list[str]
    TEAM_MEMBER_CONFIGRATIONS: dict[str, dict]

    # 运行时变量
    next: str
    full_plan: str
    deep_thinking_mode: bool
    search_before_planning: bool
```

工作流过程中会产生以下类型的事件：

| 事件类型 | 触发条件 | 内容 |
| ----- | ----- | ----- |
| on_chain_start | 代理开始执行 | 代理名称、ID |
| on_chain_end | 代理执行完成 | 代理名称、ID |
| on_chat_model_start | LLM 开始生成 | 代理名称 |
| on_chat_model_end | LLM 生成完成 | 代理名称 |
| on_chat_model_stream | LLM 生成内容片段 | 内容片段 |
| on_tool_start | 工具调用开始 | 工具名称、输入 |
| on_tool_end | 工具调用完成 | 工具名称、结果 |

## 工作流程

### 图结构

项目工作流由以下节点组成：

```text
START -> coordinator -> [planner, supervisor, researcher, coder, browser, reporter]
```

工作流程图构建代码：

```python
def build_graph():
    """Build and return the agent workflow graph."""
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", research_node)
    builder.add_node("coder", code_node)
    builder.add_node("browser", browser_node)
    builder.add_node("reporter", reporter_node)
    return builder.compile()
```

### 节点说明

| 节点 | 功能 |
| ----- | ----- |
| coordinator | 协调器节点，与用户直接通信，解析用户输入并分发任务 |
| planner | 规划器节点，生成完整的任务执行计划 |
| supervisor | 监督器节点，决定下一步应该执行哪个代理 |
| researcher | 研究员节点，执行研究任务，收集信息 |
| coder | 编码器节点，执行 Python 代码，进行数学计算 |
| browser | 浏览器节点，执行网络浏览任务 |
| reporter | 报告员节点，生成最终报告 |

## 配置

### 环境变量

项目使用环境变量配置各种设置，这些变量可以在 `.env` 文件中设置：

```conf
# Reasoning LLM (推理模型)
REASONING_API_KEY=<您的API密钥>
REASONING_MODEL=<模型名称>
REASONING_BASE_URL=<可选的API基础URL>

# Basic LLM (基础模型)
BASIC_API_KEY=<您的API密钥>
BASIC_MODEL=<模型名称>
BASIC_BASE_URL=<可选的API基础URL>

# Vision-language LLM (视觉语言模型)
VL_API_KEY=<您的API密钥>
VL_MODEL=<模型名称>
VL_BASE_URL=<可选的API基础URL>
BROWSER_USE_TEXT_ONLY=true  # 是否使用纯文本模式

# Chrome 配置
CHROME_INSTANCE_PATH=<Chrome可执行文件路径>
CHROME_HEADLESS=<是否无头模式，true/false>
CHROME_PROXY_SERVER=<代理服务器地址>
CHROME_PROXY_USERNAME=<代理用户名>
CHROME_PROXY_PASSWORD=<代理密码>

# 工具配置
TAVILY_API_KEY=<Tavily搜索API密钥>
```

### 模型配置

项目支持多种模型，包括：

1. **DeepSeek 模型**：通过 DeepSeek API 访问
2. **OpenAI 模型**：通过 OpenAI API 访问
3. **Gemini 模型**：通过 Google Generative AI API 访问（注意：某些地区可能无法访问）
4. **本地模型**：通过兼容的本地服务访问

模型配置在 `src/llms/llm.py` 中实现，支持以下模型类型：

```python
class LLMType(str, Enum):
    """LLM类型枚举"""

    BASIC = "basic"  # 基础文本模型
    REASONING = "reasoning"  # 推理模型
    VISION_LANGUAGE = "vl"  # 视觉语言模型
```

### 团队成员配置

团队成员配置在 `src/config/__init__.py` 中定义：

```python
TEAM_MEMBER_CONFIGRATIONS = {
    "researcher": { ... },
    "coder": { ... },
    "browser": { ... },
    "reporter": { ... }
}

TEAM_MEMBERS = list(TEAM_MEMBER_CONFIGRATIONS.keys())
```

每个团队成员具有以下属性：

- `name`：成员名称
- `desc`：人类可读的描述
- `desc_for_llm`：LLM 可理解的详细描述
- `is_optional`：是否可选

## 错误处理

后端API实现了以下错误处理机制：

1. **全局异常捕获**：所有API端点都包含try-except块，处理可能的异常
2. **HTTP状态码**：使用适当的HTTP状态码表示错误（如404表示资源不存在，500表示服务器错误）
3. **日志记录**：错误会被记录到日志系统中，便于调试
4. **取消处理**：支持处理客户端断开连接的情况，确保资源被正确释放

错误响应示例：

```json
{
  "detail": "Error in workflow: Your location is not supported by google-generativeai at the moment."
}
```

## 后端开发指南

本节提供了针对后端开发者的详细指南，特别关注如何扩展系统、添加新功能以及与前端协作。

### 项目架构

项目后端采用模块化设计，主要组件包括：

```bash
/src
├── api/                # API 端点定义
│   ├── __init__.py
│   └── app.py          # FastAPI 应用和路由
├── config/             # 配置文件和常量
├── graph/              # LangGraph 工作流定义
│   ├── builder.py      # 图构建器
│   ├── nodes.py        # 节点实现
│   └── types.py        # 类型定义
├── llms/               # 语言模型集成
│   └── llm.py          # LLM 工厂和缓存
├── service/            # 业务逻辑服务
│   └── workflow_service.py # 工作流服务
├── tools/              # 工具实现
│   ├── browser.py      # 浏览器工具
│   ├── search.py       # 搜索工具
│   └── bash_tool.py    # Bash 执行工具
└── utils/              # 通用工具函数
```

### 添加新API端点

要添加新的 API 端点，需要在 `src/api/app.py` 文件中进行修改。以下是添加新 API 端点的步骤和实践案例：

#### 步骤 1: 定义数据模型

使用 Pydantic 定义请求和响应模型：

```python
from pydantic import BaseModel, Field

class FileDownloadRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file to download")
    filename: Optional[str] = Field(None, description="Custom filename for the downloaded file")
```

#### 步骤 2: 实现 API 端点

```python
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
import os

# 可选：为相关端点创建路由器
# file_router = APIRouter(prefix="/api/files", tags=["files"])

@app.post("/api/files/download")
async def download_file(request: FileDownloadRequest):
    """下载指定路径的文件。
    
    Args:
        request: 包含文件路径和可选自定义文件名的请求
        
    Returns:
        文件响应对象
        
    Raises:
        HTTPException: 如果文件不存在或无法访问
    """
    try:
        file_path = request.file_path
        # 安全性检查：确保文件路径在允许的目录内
        if not is_path_allowed(file_path):
            raise HTTPException(status_code=403, detail="Access to this file path is forbidden")
            
        # 检查文件是否存在
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        # 确定文件名
        filename = request.filename or os.path.basename(file_path)
        
        # 确定媒体类型
        media_type = determine_media_type(file_path)
        
        # 返回文件
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

# 在主 app 中注册路由器
# app.include_router(file_router)
```

#### 步骤 3: 添加辅助函数

```python
def is_path_allowed(path: str) -> bool:
    """检查路径是否在允许的目录中。"""
    allowed_dirs = [
        os.path.abspath("./downloads"),
        os.path.abspath("./public"),
    ]
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(allowed_dir) for allowed_dir in allowed_dirs)

def determine_media_type(file_path: str) -> str:
    """根据文件扩展名确定媒体类型。"""
    ext = os.path.splitext(file_path)[1].lower()
    media_types = {
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".json": "application/json",
        ".csv": "text/csv",
    }
    return media_types.get(ext, "application/octet-stream")
```

### 与前端协作

后端与前端的协作是成功开发的关键。以下是一些最佳实践和模式：

#### API 契约定义

在实现新功能时，后端和前端团队应首先就 API 契约达成一致，包括：

1. **端点 URL 和方法**：定义 API 的路径和 HTTP 方法（GET、POST 等）
2. **请求参数和格式**：明确请求体、查询参数、路径参数的结构
3. **响应格式和状态码**：定义成功和错误响应的格式
4. **认证和权限要求**：明确访问 API 所需的认证机制

#### API 文档生成

项目使用 FastAPI 的自动文档生成功能。确保所有新 API 都有详细的文档字符串：

```python
@app.post("/api/data-analysis", response_model=AnalysisResponse)
async def analyze_data(request: AnalysisRequest):
    """分析提供的数据并返回见解。
    
    此端点接收数据集并执行统计分析，返回关键见解和可视化建议。
    
    Args:
        request: 包含要分析的数据的请求对象
        
    Returns:
        分析结果，包括统计指标和见解
        
    Raises:
        HTTPException(400): 如果数据格式无效
        HTTPException(422): 如果分析过程中出错
    """
    # 实现代码...
```

#### 使用 CORS 配置

项目已配置 CORS 中间件，但在添加新功能时应考虑是否需要额外配置：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],  # 可以限制为特定方法
    allow_headers=["*"],  # 可以限制为特定标头
)
```

#### 前后端通信模式

1. **RESTful API**：用于大多数标准操作
2. **Server-Sent Events (SSE)**：用于流式传输工作流进度和结果
3. **WebSocket（可选扩展）**：对于需要双向实时通信的功能

#### 为前端提供示例代码

在开发新 API 时，提供前端消费示例：

```javascript
// 示例：使用文件上传 API
async function uploadFile(file, folder = 'general') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('folder', folder);
  
  try {
    const response = await fetch('/api/files/upload', {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error uploading file:', error);
    throw error;
  }
}

// 示例：使用 SSE 流
function connectToStream() {
  const eventSource = new EventSource('/api/chat/stream');
  
  eventSource.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    console.log('Received message:', data);
    // 处理消息...
  });
  
  eventSource.addEventListener('end_of_workflow', (event) => {
    const data = JSON.parse(event.data);
    console.log('Workflow completed:', data);
    // 处理工作流结束...
    eventSource.close();
  });
  
  eventSource.onerror = (error) => {
    console.error('EventSource error:', error);
    eventSource.close();
  };
  
  return eventSource;
}
```

### 部署与测试

添加新功能后，确保进行适当的测试和部署：

#### 单元测试

为新端点和功能编写单元测试：

```python
# tests/api/test_file_api.py
import pytest
from fastapi.testclient import TestClient
from src.api.app import app
import os

client = TestClient(app)

def test_file_upload():
    # 创建测试文件
    test_file_content = b"This is a test file content"
    test_file_path = "test_file.txt"
    with open(test_file_path, "wb") as f:
        f.write(test_file_content)
    
    try:
        # 测试上传
        with open(test_file_path, "rb") as f:
            response = client.post(
                "/api/files/upload",
                files={"file": ("test.txt", f, "text/plain")},
                data={"folder": "test"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert "url" in data
        
        # 测试下载
        file_url = data["url"]
        download_response = client.get(file_url)
        assert download_response.status_code == 200
        assert download_response.content == test_file_content
    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
        upload_path = os.path.join("uploads", "test", os.path.basename(data["path"]))
        if os.path.exists(upload_path):
            os.remove(upload_path)
```

#### 集成测试

确保新功能与工作流集成良好：

```python
# tests/integration/test_workflow_with_files.py
import pytest
from src.service.workflow_service import run_agent_workflow
import asyncio
import os

@pytest.mark.asyncio
async def test_workflow_with_file_processing():
    # 创建测试文件
    test_file_content = "Sample data for analysis\n1,2,3,4,5\n6,7,8,9,10"
    test_file_path = "test_data.csv"
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(test_file_content)
    
    try:
        # 构建包含文件处理的用户消息
        messages = [
            {
                "role": "user",
                "content": f"Analyze the data in file {test_file_path} and provide statistics"
            }
        ]
        
        # 收集工作流事件
        events = []
        async for event in run_agent_workflow(messages, debug=True):
            events.append(event)
            
        # 验证关键事件
        assert any(e.get("event") == "tool_call" and 
                 e.get("data", {}).get("tool_name") == "file_processor" 
                 for e in events)
        
        # 验证最终结果包含分析
        final_state = next((e for e in events if e.get("event") == "final_session_state"), None)
        assert final_state is not None
        final_messages = final_state.get("data", {}).get("messages", [])
        assert any("statistics" in msg.get("content", "") for msg in final_messages 
                  if msg.get("role") == "assistant")
    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
```

#### 部署检查列表

在部署新功能前，请确保：

1. 所有测试都通过
2. API 文档已更新
3. 前端团队已了解新功能
4. 性能测试已完成（对于可能高负载的端点）
5. 错误处理已完善
6. 安全检查已完成（特别是对于文件操作）
