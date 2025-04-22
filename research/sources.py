"""
研究源配置 - 注册和配置所有可用的研究数据源
"""

import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage
from .research_manager import research_manager, ResearchSource
from src.tools.search import tavily_tool
from src.tools.pubmed_tool import pubmed_search
from src.crawler import Crawler
from src.agents import research_agent

logger = logging.getLogger(__name__)

def generic_research(query: str, **kwargs) -> str:
    """执行通用网络搜索，使用Tavily搜索引擎
    
    Args:
        query: 搜索查询关键词
        **kwargs: 其他参数，可能包含结果数量、过滤器等，本函数暂不使用
    """
    try:
        logger.info(f"通用网络搜索: '{query}'")
        # 这里可以使用kwargs中的参数传递给tavily_tool，但当前实现只使用query
        results = tavily_tool.invoke({"query": query})
        if not results:
            return "没有找到相关的研究内容。"
        
        markdown = "### 搜索结果\n\n"
        
        # 确保我们处理的是列表
        if isinstance(results, list):
            for i, result in enumerate(results, 1):
                if isinstance(result, dict):
                    title = result.get('title', '未知标题')
                    content = result.get('content', '无内容')
                    url = result.get('url', '#')
                    
                    markdown += f"#### {i}. {title}\n\n"
                    markdown += f"{content}\n\n"
                    markdown += f"[链接]({url})\n\n"
                    markdown += "---\n\n"
                else:
                    # 如果结果项不是字典，尝试将其作为纯文本处理
                    markdown += f"#### {i}. 搜索结果\n\n"
                    markdown += f"{str(result)}\n\n"
                    markdown += "---\n\n"
        else:
            # 如果不是列表，直接显示结果
            markdown += f"搜索结果: {str(results)}\n\n"
        
        logger.info("通用搜索完成")
        return markdown
    except Exception as e:
        logger.error(f"通用研究搜索失败: {str(e)}")
        return f"搜索过程中发生错误: {str(e)}"

def agent_research(query: str, **kwargs) -> str:
    """执行代理研究，调用research_agent进行更深入的分析
    
    Args:
        query: 搜索查询关键词
        **kwargs: 其他参数，可能包含 state、num_results 等
    """
    # 仅使用所需参数 - 这里那个函数需要state
    if "state" in kwargs:
        state = kwargs["state"]
    else:
        state = {
            "messages": [HumanMessage(content=query)],
        }
    try:
        result = research_agent.invoke(state)
        return result["messages"][-1].content
    except Exception as e:
        logger.error(f"代理研究失败: {str(e)}")
        return f"研究代理执行失败: {str(e)}"

def web_crawler(url: str, **kwargs) -> str:
    """爬取特定网页的内容"""
    try:
        crawler = Crawler()
        article = crawler.crawl(url)
        return article.to_markdown()
    except Exception as e:
        logger.error(f"网页爬取失败: {str(e)}")
        return f"网页爬取失败: {str(e)}"

def register_default_sources():
    """注册默认的研究数据源"""
    # 注册Tavily通用搜索
    research_manager.register_source(ResearchSource(
        name="通用搜索",
        description="使用Tavily搜索引擎进行通用网络搜索",
        handler=generic_research,
        weight=0.7
    ))
    
    # 注册PubMed医学文献搜索
    research_manager.register_source(ResearchSource(
        name="PubMed医学文献",
        description="搜索PubMed医学文献数据库中的专业医学研究论文",
        handler=pubmed_search,
        weight=1.0  # 医学专业内容，给予最高权重
    ))
    
    # 注册代理研究
    research_manager.register_source(ResearchSource(
        name="AI分析研究",
        description="使用AI代理进行深度分析和研究",
        handler=agent_research,
        weight=0.8
    ))
    
    logger.info("已注册默认研究数据源")

# 在模块加载时注册默认数据源
register_default_sources()
