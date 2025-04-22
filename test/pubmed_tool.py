"""
提供PubMed文献摘要爬取工具
"""

import os
import re
import asyncio
import logging
import tempfile
from typing import Annotated, List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from langchain_core.tools import tool
from pydantic import BaseModel
from .decorators import log_io

logger = logging.getLogger(__name__)

class PubMedResult(BaseModel):
    """PubMed搜索结果模型"""
    pmid: str
    title: Optional[str] = None
    abstract: str
    url: str

async def fetch_pubmed_abstracts(query: str, num_results: int = 5, max_page: int = 10) -> List[PubMedResult]:
    """
    异步获取PubMed文章摘要
    
    Args:
        query: 搜索关键词
        num_results: 需要的结果数量
        max_page: 最大页数限制
        
    Returns:
        文章摘要列表
    """
    encoded_query = quote_plus(query)
    results = []
    page = 1
    
    # 创建一个临时目录存储下载的内容
    with tempfile.TemporaryDirectory() as temp_dir:
        while len(results) < num_results and page <= max_page:
            logger.info(f"处理PubMed第{page}页...")
            url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}&page={page}"
            
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.text
                
                # 提取文章链接
                pat1_content_url = '<div class="docsum-wrap">.*?<.*?href="(.*?)".*?</a>'
                content_url = re.compile(pat1_content_url, re.S).findall(data)
                
                if not content_url:
                    logger.info(f"PubMed第{page}页没有找到文章链接，可能已到达最后一页")
                    break
                
                hd = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                for article_url in content_url:
                    if len(results) >= num_results:
                        break
                    
                    full_url = "https://pubmed.ncbi.nlm.nih.gov" + article_url
                    
                    try:
                        article_data = requests.get(full_url, headers=hd).text
                        
                        # 提取PMID
                        pmid_match = re.search(r'/([0-9]+)/?', article_url)
                        if not pmid_match:
                            continue
                        
                        pmid = pmid_match.group(1)
                        
                        # 提取标题
                        title_pattern = r'<h1 class="heading-title">(.*?)</h1>'
                        title_match = re.search(title_pattern, article_data, re.S)
                        title = title_match.group(1).strip() if title_match else "未获取到标题"
                        
                        # 提取摘要
                        abstract_found = False
                        pat3_content = '<div class="abstract-content selected".*?>(.*?)</div>'
                        content_html = re.compile(pat3_content, re.S).findall(article_data)
                        
                        if content_html:
                            # 使用BeautifulSoup解析找到的HTML，并获取纯文本内容
                            soup = BeautifulSoup(content_html[0], 'html.parser')
                            abstract = soup.get_text(strip=True)
                            abstract_found = True
                        else:
                            # 尝试使用BeautifulSoup直接从页面提取摘要
                            soup = BeautifulSoup(article_data, 'html.parser')
                            abstract_div = soup.select_one('.abstract-content')
                            if abstract_div:
                                abstract = abstract_div.get_text(strip=True)
                                abstract_found = True
                            else:
                                logger.info(f"文章 {pmid} 可能没有摘要，跳过")
                                continue
                        
                        if abstract_found:
                            results.append(PubMedResult(
                                pmid=pmid,
                                title=title,
                                abstract=abstract,
                                url=full_url
                            ))
                            logger.info(f"成功获取PubMed文章 {pmid}: {title[:30]}...")
                    
                    except Exception as err:
                        logger.error(f"处理PubMed文章 {full_url} 时出现错误: {err}")
                
                page += 1
                
            except Exception as err:
                logger.error(f"处理PubMed第{page}页时出现错误: {err}")
                page += 1
    
    return results

# 先定义原始函数，不使用装饰器
def _pubmed_search_impl(
    query: str,
    num_results: int = 5
) -> str:
    """
    使用此工具从PubMed搜索和获取医学研究文献的摘要。
    PubMed是美国国家生物技术信息中心(NCBI)提供的一个免费搜索引擎，
    主要访问MEDLINE数据库中的生物医学文献参考书目和摘要。

    参数:
        query: 搜索关键词
        num_results: 需要获取的结果数量，默认为5
    
    返回:
        包含PubMed文献摘要的markdown格式文本
    """
    try:
        logger.info(f"开始从PubMed搜索: '{query}', 获取 {num_results} 篇文献")
        # 使用同步方式调用异步函数
        results = asyncio.run(fetch_pubmed_abstracts(query, num_results))
        
        if not results:
            return f"在PubMed中未找到与'{query}'相关的结果。"
        
        # 构建Markdown格式输出
        markdown = f"## PubMed 搜索结果: '{query}'\n\n"
        markdown += f"找到 {len(results)} 篇相关文献：\n\n"
        
        for i, result in enumerate(results, 1):
            markdown += f"### {i}. {result.title}\n"
            markdown += f"**PMID**: {result.pmid} | [在PubMed查看]({result.url})\n\n"
            markdown += f"**摘要**:\n{result.abstract}\n\n"
            markdown += "---\n\n"
        
        logger.info(f"成功从PubMed获取 {len(results)} 篇文献")
        return markdown
    
    except Exception as e:
        error_msg = f"PubMed搜索失败: {str(e)}"
        logger.error(error_msg)
        return error_msg

# 将原实现函数包装为工具
@tool
@log_io
def pubmed_tool(
    query: Annotated[str, "搜索查询关键词"],
    num_results: Annotated[int, "需要获取的结果数量，默认为5"] = 5
) -> str:
    """
    使用此工具从PubMed搜索和获取医学研究文献的摘要。
    
    Args:
        query: 要搜索的医学关键词或知识点
        num_results: 需要获取的文献数量，默认为5篇
    
    Returns:
        Markdown格式的文献摘要信息
    """
    return _pubmed_search_impl(query, num_results)

# 同步版本封装，用于与非异步框架的兼容
def pubmed_search(query: str, **kwargs) -> str:
    """同步版本的PubMed搜索工具，用于与非异步框架的兼容
    
    Args:
        query: 搜索查询关键词
        **kwargs: 其他参数，包含num_results或其他选项
    """
    # 仅使用工具所需参数，不进行工具调用，而是直接调用原始实现
    num_results = kwargs.get("num_results", 5)
    # 直接调用实现函数，绕过工具装饰器
    return _pubmed_search_impl(query, num_results)
