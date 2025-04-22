import asyncio
import logging
import json
import os
from pydantic import BaseModel, Field
from typing import Optional, ClassVar, Type, Dict, Any, Union
from langchain.tools import BaseTool
from browser_use import AgentHistoryList, Browser, BrowserConfig
from browser_use import Agent as BrowserAgent
from src.llms.llm import vl_llm, basic_llm
from src.tools.decorators import create_logged_tool
from src.config import (
    CHROME_INSTANCE_PATH,
    CHROME_HEADLESS,
    CHROME_PROXY_SERVER,
    CHROME_PROXY_USERNAME,
    CHROME_PROXY_PASSWORD,
    BROWSER_HISTORY_DIR,
)
import uuid

# Configure logging
logger = logging.getLogger(__name__)

browser_config = BrowserConfig(
    headless=CHROME_HEADLESS,
    chrome_instance_path=CHROME_INSTANCE_PATH,
)
if CHROME_PROXY_SERVER:
    proxy_config = {
        "server": CHROME_PROXY_SERVER,
    }
    if CHROME_PROXY_USERNAME:
        proxy_config["username"] = CHROME_PROXY_USERNAME
    if CHROME_PROXY_PASSWORD:
        proxy_config["password"] = CHROME_PROXY_PASSWORD
    browser_config.proxy = proxy_config

expected_browser = Browser(config=browser_config)


class BrowserUseInput(BaseModel):
    """Input for WriteFileTool."""

    instruction: str = Field(..., description="The instruction to use browser")


class BrowserTool(BaseTool):
    name: ClassVar[str] = "browser"
    args_schema: Type[BaseModel] = BrowserUseInput
    description: ClassVar[str] = (
        "Use this tool to interact with web browsers. Input should be a natural language description of what you want to do with the browser, such as 'Go to google.com and search for browser-use', or 'Navigate to Reddit and find the top post about AI'."
    )

    _agent: Optional[BrowserAgent] = None
    
    # 检查是否使用纯文本模式（没有视觉能力）
    @property
    def text_only_mode(self) -> bool:
        return os.environ.get("BROWSER_USE_TEXT_ONLY", "").lower() in ["true", "1", "yes", "y"]

    def _generate_browser_result(
        self, result_content: str, generated_gif_path: str
    ) -> dict:
        return {
            "result_content": result_content,
            "generated_gif_path": generated_gif_path,
        }

    def _run(self, instruction: str) -> str:
        generated_gif_path = f"{BROWSER_HISTORY_DIR}/{uuid.uuid4()}.gif"
        """Run the browser task synchronously."""
        
        # 根据是否启用纯文本模式选择不同的LLM
        if self.text_only_mode:
            # 纯文本模式 - 使用基础模型，禁用视觉功能
            logger.info("启用浏览器纯文本模式 - 使用基础LLM而非视觉模型")
            self._agent = BrowserAgent(
                task=instruction,
                llm=basic_llm,  # 使用基础文本模型
                browser=expected_browser,
                generate_gif=generated_gif_path,
                use_vision=False
            )
        else:
            # 视觉模式 - 使用视觉模型
            logger.info("启用浏览器视觉模式 - 使用视觉LLM")
            self._agent = BrowserAgent(
                task=instruction,
                llm=vl_llm,
                browser=expected_browser,
                generate_gif=generated_gif_path,
            )

        # 使用当前事件循环或创建新循环，避免创建过多循环
        try:
            # 首先尝试获取现有循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    logger.warning("现有事件循环已关闭，创建新的事件循环")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                # 如果没有事件循环，创建一个新的
                logger.info("没有活动的事件循环，创建新的事件循环")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            # 运行浏览器任务
            result = loop.run_until_complete(self._agent.run())
            
            # 处理结果
            if isinstance(result, AgentHistoryList):
                return json.dumps(
                    self._generate_browser_result(
                        result.final_result(), generated_gif_path
                    )
                )
            else:
                return json.dumps(
                    self._generate_browser_result(result, generated_gif_path)
                )
        # 注意：我们不关闭事件循环，避免影响后续可能的异步操作
        except Exception as e:
            return f"Error executing browser task: {str(e)}"

    async def terminate(self):
        """Terminate the browser agent if it exists."""
        if self._agent and self._agent.browser:
            try:
                await self._agent.browser.close()
            except Exception as e:
                logger.error(f"Error terminating browser agent: {str(e)}")
        self._agent = None

    async def _arun(self, instruction: str) -> str:
        """Run the browser task asynchronously."""
        generated_gif_path = f"{BROWSER_HISTORY_DIR}/{uuid.uuid4()}.gif"
        self._agent = BrowserAgent(
            task=instruction,
            llm=vl_llm,
            browser=expected_browser,
            generate_gif=generated_gif_path,  # Will be set per request
        )
        try:
            result = await self._agent.run()
            if isinstance(result, AgentHistoryList):
                return json.dumps(
                    self._generate_browser_result(
                        result.final_result(), generated_gif_path
                    )
                )
            else:
                return json.dumps(
                    self._generate_browser_result(result, generated_gif_path)
                )
        except Exception as e:
            return f"Error executing browser task: {str(e)}"
        finally:
            await self.terminate()


BrowserTool = create_logged_tool(BrowserTool)
browser_tool = BrowserTool()

if __name__ == "__main__":
    browser_tool._run(instruction="go to github.com and search DeepMedical")
