"""
FastAPI application for DeepMedical.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional, Union

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from poetry.console.commands import self
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import asyncio
from typing import AsyncGenerator, Dict, List, Any
from sqlalchemy.orm import Session

from src.graph import build_graph
from src.config import TEAM_MEMBERS, TEAM_MEMBER_CONFIGRATIONS, BROWSER_HISTORY_DIR
from src.service.workflow_service import run_agent_workflow
from src.service.markdown_service import MarkdownService
from src.service.session_service import SessionService
from src.database.db import get_db
from starlette.responses import JSONResponse
import re
from urllib.parse import quote
from datetime import datetime
# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    docs_url="/docs",
    swagger_js_url="/static/swagger-ui-bundle.js",
    swagger_css_url="/static/swagger-ui.css",
    title="DeepMedical API",
    description="API for DeepMedical LangGraph-based agent workflow",
    version="0.1.0",
)
markdown_service = MarkdownService()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],# Allows all headers
    expose_headers=["Content-Disposition"]  # 允许前端读取下载头

)

# Create the graph
graph = build_graph()


class ContentItem(BaseModel):
    type: str = Field(..., description="The type of content (text, image, etc.)")
    text: Optional[str] = Field(None, description="The text content if type is 'text'")
    image_url: Optional[str] = Field(
        None, description="The image URL if type is 'image'"
    )


class ChatMessage(BaseModel):
    role: str = Field(
        ..., description="The role of the message sender (user or assistant)"
    )
    content: Union[str, List[ContentItem]] = Field(
        ...,
        description="The content of the message, either a string or a list of content items",
    )


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="The conversation history")
    debug: Optional[bool] = Field(False, description="Whether to enable debug logging")
    deep_thinking_mode: Optional[bool] = Field(
        False, description="Whether to enable deep thinking mode"
    )
    search_before_planning: Optional[bool] = Field(
        False, description="Whether to search before planning"
    )
    team_members: Optional[list] = Field(None, description="enabled team members")
    session_id: Optional[str] = Field(None, description="Session ID for continuing a conversation")


# 会话模型
class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime

# 创建会话请求
class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = None

# 会话历史响应
class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    state: Optional[Dict[str, Any]] = None


@app.post("/api/chat/stream")
async def chat_endpoint(request: ChatRequest, req: Request):
    """
    Chat endpoint for LangGraph invoke.

    Args:
        request: The chat request
        req: The FastAPI request object for connection state checking

    Returns:
        The streamed response
    """
    try:
        # Convert Pydantic models to dictionaries and normalize content format
        messages = []
        for msg in request.messages:
            message_dict = {"role": msg.role}

            # Handle both string content and list of content items
            if isinstance(msg.content, str):
                message_dict["content"] = msg.content
            else:
                # For content as a list, convert to the format expected by the workflow
                content_items = []
                for item in msg.content:
                    if item.type == "text" and item.text:
                        content_items.append({"type": "text", "text": item.text})
                    elif item.type == "image" and item.image_url:
                        content_items.append(
                            {"type": "image", "image_url": item.image_url}
                        )

                message_dict["content"] = content_items

            messages.append(message_dict)

        async def event_generator():
            try:
                # 传递session_id参数
                session_id = None
                async for event in run_agent_workflow(
                    messages,
                    request.debug,
                    request.deep_thinking_mode,
                    request.search_before_planning,
                    request.team_members,
                    request.session_id,  # 传递session_id
                ):
                    # 获取返回的session_id
                    if event.get("type") == "session_id" or event.get("event") == "session_id":
                        # 兼容两种事件格式
                        session_id = event.get("data", {}).get("session_id")
                    
                    # Check if client is still connected
                    if await req.is_disconnected():
                        logger.info("Client disconnected, stopping workflow")
                        break
                    # 兼容两种事件格式
                    event_type = event.get("type") or event.get("event")
                    event_data = event.get("data", {})
                    
                    yield {
                        "event": event_type,
                        "data": json.dumps(event_data, ensure_ascii=False),
                    }
                
                # 在最后一个事件后返回session_id
                if session_id:
                    # 手动格式化SSE字符串，确保正确的格式
                    event_name = "session_id"
                    data_payload = json.dumps({"session_id": session_id}, ensure_ascii=False)
                    sse_message = f"event: {event_name}\ndata: {data_payload}\n\n"
                    logger.info(f"Yielding session_id event for session: {session_id}")
                    yield sse_message
            except asyncio.CancelledError:
                logger.info("Stream processing cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in workflow: {e}")
                raise

        return EventSourceResponse(
            event_generator(),
            media_type="text/event-stream",
            sep="\n",
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browser_history/{filename}")
async def get_browser_history_file(filename: str):
    """
    Get a specific browser history GIF file.

    Args:
        filename: The filename of the GIF to retrieve

    Returns:
        The GIF file
    """
    try:
        file_path = os.path.join(BROWSER_HISTORY_DIR, filename)
        if not os.path.exists(file_path) or not filename.endswith(".gif"):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(file_path, media_type="image/gif", filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving browser history file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/team_members")
async def get_team_members():
    """
    Get the configuration of all team members.

    Returns:
        dict: A dictionary containing team member configurations
    """
    try:
        return {"team_members": TEAM_MEMBER_CONFIGRATIONS}
    except Exception as e:
        logger.error(f"Error getting team members: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# 创建新会话
@app.post("/api/session", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest, 
    db: Session = Depends(get_db)
):
    """创建新会话"""
    try:
        session = await SessionService.create_session(db, request.user_id)
        return {
            "id": session.id,
            "created_at": session.created_at,
            "updated_at": session.updated_at
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 初始化聊天会话
@app.post("/api/chat/initiate", response_model=dict)
async def initiate_chat(
    request: dict, 
    req: Request,
    db: Session = Depends(get_db)
):
    """初始化聊天会话，创建会话ID并处理第一条消息
    
    Args:
        request: 包含用户第一条消息和配置的请求
        req: FastAPI请求对象
        db: 数据库会话
        
    Returns:
        包含会话ID和初始响应的字典
    """
    try:
        # 创建新会话
        session = await SessionService.create_session(db)
        session_id = session.id
        logger.info(f"Created new session: {session_id}")
        
        # 构造消息
        message = {
            "role": "user",
            "content": request.get("message", "")
        }
        
        # 保存第一条消息
        await SessionService.add_message(
            db, 
            session_id=session_id,
            role=message["role"],
            content=message["content"],
            message_type="text"  # 显式指定消息类型为text
        )
        
        return {
            "session_id": session_id,
            "initial_messages": [],  # 如果需要立即返回初始回复，可以在这里添加
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error initiating chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 获取会话历史
@app.get("/api/session/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str, 
    db: Session = Depends(get_db)
):
    """获取会话历史"""
    try:
        # 获取会话
        session = await SessionService.get_session(db, session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # 获取会话消息
        messages = await SessionService.get_session_messages(db, session_id)
        formatted_messages = await SessionService.format_messages_for_frontend(messages)
        
        # 确保state字段存在
        state = session.state if session.state else {}
        
        # 记录详细日志
        logger.info(f"Retrieved history for session {session_id}: {len(formatted_messages)} messages")
        logger.debug(f"Session state: {state}")
        
        return {
            "session_id": session_id,
            "messages": formatted_messages,
            "state": state
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save-as-markdown")
async def save_as_markdown(article_data: dict):
    """保存文章为Markdown文件"""
    try:
        # 参数校验
        required_fields = ["filename", "content"]
        for field in required_fields:
            if field not in article_data:
                raise HTTPException(400, detail=f"Missing required field: {field}")

        # 调用服务保存
        result = markdown_service.save_article_as_markdown(article_data)

        if result["status"] == "error":
            raise HTTPException(400, detail=result)

        return JSONResponse(content=result)

    except HTTPException as he:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# 修改下载接口为查询参数形式
@app.get("/api/download/markdown")
async def download_markdown(filename: str):
    try:
        # 严格匹配存储的文件名格式
        if not re.match(r"^[\w\u4e00-\u9fa5\-_.]+\.md$", filename):
            raise HTTPException(400, "无效文件名格式")

        filepath = markdown_service.output_dir / filename

        # 增强存在性检查
        if not filepath.is_file():
            raise HTTPException(404, detail={
                "error_code": "FILE_NOT_FOUND",
                "suggested": "使用/api/list获取有效文件列表"
            })

        # 记录下载日志
        logger.info(f"下载文件: {filename} 大小: {filepath.stat().st_size}字节")
        return FileResponse(filepath)

    except HTTPException as he:
        raise
    except ValueError as ve:
        raise HTTPException(400, detail=str(ve))
    except Exception as e:
        raise HTTPException(500, detail=str(e))