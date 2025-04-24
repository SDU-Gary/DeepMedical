"""
FastAPI application for DeepMedical.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import asyncio
from typing import AsyncGenerator, Dict, List, Any

from src.graph import build_graph
from src.config import TEAM_MEMBERS, TEAM_MEMBER_CONFIGRATIONS, BROWSER_HISTORY_DIR
from src.service.workflow_service import run_agent_workflow
from src.service.markdown_service import MarkdownService
from starlette.responses import JSONResponse
import re
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
                async for event in run_agent_workflow(
                    messages,
                    request.debug,
                    request.deep_thinking_mode,
                    request.search_before_planning,
                    request.team_members,
                ):
                    # Check if client is still connected
                    if await req.is_disconnected():
                        logger.info("Client disconnected, stopping workflow")
                        break
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"], ensure_ascii=False),
                    }
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


markdown_service = MarkdownService()

@app.post("/api/save-as-markdown")
async def save_as_markdown(article_data: dict):
    """保存文章为Markdown文件"""
    try:
        # 参数校验
        if not article_data.get("title") or not article_data.get("content"):
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "标题和内容不能为空"}
            )

        # 生成安全文件名（使用正则表达式清理）
        clean_title = re.sub(r'[^\w\u4e00-\u9fa5-]', '_', article_data["title"])[:50]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{clean_title}_{timestamp}.md"

        # 调用服务层
        result = markdown_service.save_article_as_markdown({
            "filename": filename,
            "content": article_data["content"]
        })

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result)

        return JSONResponse(content=result)

    except HTTPException as he:
        raise
    except Exception as e:
        logger.error(f"保存失败: {str(e)}", exc_info=True)  # 添加详细异常日志
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "文件保存失败"}
        )

# 修改下载接口为查询参数形式
@app.get("/api/download/markdown")
async def download_markdown(filename: str):
    try:
        # 路径安全检查
        if "../" in filename:
            raise HTTPException(status_code=400, detail="非法文件名")

        save_dir = os.path.abspath("output/markdowns")
        filepath = os.path.join(save_dir, filename)

        if not os.path.exists(filepath):
            logger.error(f"文件未找到: {filename}")
            raise HTTPException(status_code=404, detail="文件不存在")

        return FileResponse(
            filepath,
            media_type="application/octet-stream",
            filename=filename
        )
    except HTTPException as he:
        raise
    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")