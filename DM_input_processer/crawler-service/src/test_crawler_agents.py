"""
爬虫Agent简单测试脚本

这个脚本直接测试PlaywrightAgent和ScrapyAgent的基本功能，
不依赖其他组件，便于快速验证爬虫功能是否正常。
"""

import asyncio
import logging
import time
from typing import Dict, List, Any
import os
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_crawler_agents")

# 导入Agent实现
from agents.playwright_agent.agent import PlaywrightAgent
from agents.scrapy_agent.agent import ScrapyAgent

# 测试URL列表
TEST_URLS = [
    # 静态页面测试 (适合ScrapyAgent)
    {"url": "https://www.python.org/", "name": "Python官网(静态)"},
    {"url": "https://www.gnu.org/", "name": "GNU官网(静态)"},
    
    # 动态页面测试 (适合PlaywrightAgent)
    {"url": "https://www.baidu.com/", "name": "百度(动态)"},
    {"url": "https://www.zhihu.com/", "name": "知乎(动态)"},
]

async def test_playwright_agent():
    """测试PlaywrightAgent"""
    logger.info("开始测试PlaywrightAgent...")
    
    agent = PlaywrightAgent()
    try:
        # 初始化Agent
        await agent.initialize()
        logger.info("PlaywrightAgent初始化成功")
        
        # 测试动态页面
        for test_case in TEST_URLS[2:]:  # 使用动态页面测试
            url = test_case["url"]
            name = test_case["name"]
            logger.info(f"开始测试PlaywrightAgent抓取: {name} - {url}")
            
            # 准备配置
            strategy = {
                "render_js": True,
                "wait_for_full_load": True,
                "emulate_user_interaction": True,
                "extract_metadata": True,
                "block_resources": False,  # 明确设置不阻止资源
                "wait_until": "networkidle",  # 明确设置等待条件
                "extract_links": True,
                "capture_screenshot": False
            }
            
            execution_config = {
                "proxy": None,
                "timeout": 30,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
                "behavior": {
                    "scroll": True,
                    "wait_time": 2,
                    "click_elements": False
                }
            }
            
            start_time = time.time()
            result = await agent.fetch(url, strategy, execution_config)
            elapsed = time.time() - start_time
            
            # 打印结果摘要
            if result.get("success"):
                content_len = len(result.get("content", ""))
                title = result.get("title", "无标题")
                logger.info(f"PlaywrightAgent抓取成功: {name}")
                logger.info(f"  标题: {title}")
                logger.info(f"  内容长度: {content_len} 字符")
                logger.info(f"  耗时: {elapsed:.2f} 秒")
                logger.info(f"  提取链接数: {len(result.get('extracted_links', []))}")
            else:
                logger.error(f"PlaywrightAgent抓取失败: {name}")
                logger.error(f"  错误: {result.get('error', '未知错误')}")
            
            # 等待一下，避免请求过快
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"PlaywrightAgent测试出错: {e}")
    finally:
        # 关闭Agent
        await agent.shutdown()
        logger.info("PlaywrightAgent已关闭")

async def test_scrapy_agent():
    """测试ScrapyAgent"""
    logger.info("开始测试ScrapyAgent...")
    
    agent = ScrapyAgent()
    try:
        # 初始化Agent
        await agent.initialize()
        logger.info("ScrapyAgent初始化成功")
        
        # 测试静态页面
        for test_case in TEST_URLS[:2]:  # 使用静态页面测试
            url = test_case["url"]
            name = test_case["name"]
            logger.info(f"开始测试ScrapyAgent抓取: {name} - {url}")
            
            # 准备配置
            strategy = {
                "render_js": False,
                "extract_links": True,
                "extract_metadata": True
            }
            
            execution_config = {
                "proxy": None,
                "timeout": 20,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            }
            
            start_time = time.time()
            result = await agent.fetch(url, strategy, execution_config)
            elapsed = time.time() - start_time
            
            # 打印结果摘要
            if result.get("success"):
                content_len = len(result.get("content", ""))
                title = result.get("title", "无标题")
                logger.info(f"ScrapyAgent抓取成功: {name}")
                logger.info(f"  标题: {title}")
                logger.info(f"  内容长度: {content_len} 字符")
                logger.info(f"  耗时: {elapsed:.2f} 秒")
                logger.info(f"  提取链接数: {len(result.get('extracted_links', []))}")
            else:
                logger.error(f"ScrapyAgent抓取失败: {name}")
                logger.error(f"  错误: {result.get('error', '未知错误')}")
            
            # 等待一下，避免请求过快
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"ScrapyAgent测试出错: {e}")
    finally:
        # 关闭Agent
        await agent.shutdown()
        logger.info("ScrapyAgent已关闭")

async def main():
    """主测试函数"""
    logger.info("开始爬虫Agent测试...")
    
    # 先测试ScrapyAgent
    await test_scrapy_agent()
    
    # 再测试PlaywrightAgent
    await test_playwright_agent()
    
    logger.info("爬虫Agent测试完成")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
