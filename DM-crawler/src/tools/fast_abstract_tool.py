"""
快速医学文献摘要搜索工具，整合多源信息检索

此工具利用LangChain的回调机制实时反馈研究进度
"""


import re
import asyncio
import logging

from typing import List, Optional
from urllib.parse import quote_plus
import httpx

from googletrans import Translator
from langchain_core.tools import BaseTool
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
import requests

from src.tools.pubmed_crawle import run_pubmed

from src.tools.decorators import create_logged_tool

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br', # httpx/requests 会处理解压
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin', # 或 'none' 取决于场景
    'Sec-Fetch-User': '?1',
}

# 配置更详细的日志记录
logger = logging.getLogger(__name__)

# 确保日志级别是DEBUG，以显示所有调试信息
logger.setLevel(logging.DEBUG)

# 添加控制台处理器，确保日志会打印到控制台
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
logger.debug("fast_abstract_tool模块已加载")

class PubMedResult(BaseModel):
    """PubMed搜索结果模型"""
    pmid: str
    title: Optional[str] = None
    abstract: str
    url: str

class FastAbstractToolInput(BaseModel):
    """医学文献快速搜索工具的输入模型"""
    query: str = Field(..., description="搜索关键词或医学问题")
    num_results: int = Field(5, description="需要的结果数量")
    sources: List[str] = Field(default=["pubmed"], description="要搜索的来源，可选值包括：pubmed, google_scholar, medline等")

class FastAbstractTool(BaseTool):
    name: str = "fast_abstract_tool"
    description: str = "..." # 省略
    args_schema = FastAbstractToolInput

    # --- 同步 _run 方法 (尝试用 asyncio.run 调用 _arun) ---
    def _run(
        self,
        query: str,
        num_results: int = 5,
        sources: List[str] = ["pubmed"],
        run_manager: Optional[CallbackManagerForToolRun] = None # 接收同步 Callback Manager
    ) -> str:
        """
        同步执行入口。尝试在当前线程使用 asyncio.run() 执行异步版本 _arun。
        注意：这可能会丢失 _arun 中的中间回调进度。
        """
        logger.warning(f"Tool '{self.name}' called synchronously (_run). Attempting to execute asynchronous version (_arun) using asyncio.run(). Intermediate callbacks may be lost.")

        # 报告一个初始状态（可选），因为 _arun 的回调不会被触发
        if run_manager:
            run_manager.on_text("同步调用，开始执行异步核心逻辑...\n", verbose=True)

        try:
            # asyncio.run() 会在此线程中创建、运行并关闭一个新的事件循环
            result = asyncio.run(self._arun(
                query=query,
                num_results=num_results,
                sources=sources,
                run_manager=None # 显式将 run_manager 设置为 None
            ))
            if run_manager:
                 run_manager.on_text("异步核心逻辑执行完毕。\n", verbose=True)
            return result
        except Exception as e:
            logger.error(f"Failed to execute _arun using asyncio.run() from _run: {e}", exc_info=True)
            # 向 LangChain 框架返回一个有意义的错误信息
            error_message = f"Error: Tool execution failed during synchronous fallback. Details: {e}"
            # 也可以尝试通过 run_manager 报告错误，如果 run_manager 存在
            if run_manager:
                 run_manager.on_text(f"❌ {error_message}\n", verbose=True)
            # 返回错误信息或者根据需要抛出异常（但这可能中断流程）
            return error_message # 返回错误信息字符串通常更安全


    # --- 需要创建一个同步的 PubMed 获取方法 ---
    def _fetch_pubmed_abstracts_sync(
        self,
        query: str,
        num_results: int = 5,
        max_page: int = 10,
        run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> List[PubMedResult]:
        """(同步版本) 获取PubMed文章摘要"""
        logger.debug(f"[调试] _fetch_pubmed_abstracts_sync: query={query}, num_results={num_results}")
        encoded_query = quote_plus(query)
        results = []
        page = 1

        # 使用 requests 进行同步请求
        with requests.Session() as session: # 使用 Session 保持连接
             session.headers.update({'User-Agent': '...'}) # 设置 User-Agent
             while len(results) < num_results and page <= max_page:
                if run_manager:
                    run_manager.on_text(f"正在搜索PubMed第{page}页...\n", verbose=True)

                url = f"https://pubmed.ncbi.nlm.nih.gov/?term={encoded_query}&page={page}"
                try:
                    response = session.get(url, timeout=20.0) # 设置超时
                    response.raise_for_status()
                    data = response.text

                    # ... (提取链接、标题、摘要的逻辑基本不变) ...
                    pat1_content_url = '<div class="docsum-wrap">.*?<.*?href="(.*?)".*?</a>'
                    content_url = re.compile(pat1_content_url, re.S).findall(data)

                    if not content_url:
                        # ... (处理无结果) ...
                        break

                    for idx, article_url in enumerate(content_url):
                        if len(results) >= num_results: break
                        full_url = "https://pubmed.ncbi.nlm.nih.gov" + article_url

                        if run_manager and idx % 3 == 0:
                             # ... (报告进度) ...
                             run_manager.on_text(f"正在获取文献 {len(results)+1}/{num_results}...\n", verbose=True)

                        try:
                            article_response = session.get(full_url, timeout=20.0)
                            article_response.raise_for_status()
                            article_data = article_response.text
                            # ... (提取 PMID, title, abstract) ...
                            # 假设提取逻辑不变
                            pmid = "..."
                            title = "..."
                            abstract = "..."
                            abstract_found = True

                            if abstract_found:
                                results.append(PubMedResult(pmid=pmid, title=title, abstract=abstract, url=full_url))
                                if run_manager:
                                     run_manager.on_text(f"✓ 已获取: {title[:40]}...\n", verbose=True)

                        except requests.exceptions.RequestException as req_err:
                             logger.error(f"获取文章详情请求错误 {full_url}: {req_err}")
                             if run_manager: run_manager.on_text(f"获取文章 {pmid} 详情失败 (请求错误)，继续\n", verbose=True)
                        except Exception as err:
                            logger.error(f"处理PubMed文章 {full_url} 时出现错误: {err}", exc_info=True)
                            if run_manager: run_manager.on_text(f"获取文章详情失败，继续尝试下一篇\n", verbose=True)

                    page += 1

                except requests.exceptions.RequestException as req_err: # 处理列表页请求错误
                    logger.error(f"请求PubMed第{page}页时出错: {req_err}")
                    if run_manager: run_manager.on_text(f"搜索PubMed第{page}页请求出错，尝试下一页\n", verbose=True)
                    page += 1
                except Exception as err: # 捕获其他意外错误
                    logger.error(f"处理PubMed第{page}页时出现未知错误: {err}", exc_info=True)
                    if run_manager: run_manager.on_text(f"搜索PubMed第{page}页出错，尝试下一页\n", verbose=True)
                    page += 1
        return results


    # --- 异步 _arun 方法 ---
    async def _arun(
        self,
        query: str,
        num_results: int = 5,
        sources: List[str] = ["pubmed"],
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None # 注意类型是 Async*
    ) -> str:
        """异步运行医学文献搜索工具"""
        logger.debug(f"[FastAbstractTool] _arun 方法被调用: 查询={query}, 结果数量={num_results}, 来源={sources}")
        logger.debug(f"[FastAbstractTool] run_manager 类型: {type(run_manager)}")

        translator = Translator() # 每次调用创建实例可能不是最高效的，可以考虑类级别或全局实例
        original_query = query
        translation_query = query # 默认不翻译

        # 检查是否有中文并进行翻译
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
        if has_chinese:
            if run_manager:
                await run_manager.on_text(f"原始查询: '{query}'\n", verbose=True)
            try:
                logger.debug(f"尝试翻译查询: '{query}'")
                # --- 使用 await 调用异步翻译 ---
                translation_query = translator.translate(query, dest='en', src='auto')
                # translation_query = translation_query.text

                logger.debug(f"查询已翻译为英文: '{translation_query}'")
                if run_manager:
                    await run_manager.on_text(f"查询已翻译为英文: '{translation_query}'\n", verbose=True)
            except Exception as e:
                logger.error(f"翻译查询时出错: {e}")
                if run_manager:
                    await run_manager.on_text(f"❌ 翻译查询失败: {e}\n", verbose=True)
                # 可以选择是继续使用原始查询还是返回错误
                # translated_query = query # 回退到原始查询

        # 后续逻辑使用 translated_query
        query_to_use = translation_query

        all_results = []
        if run_manager:
            await run_manager.on_text("开始医学文献搜索...\n", verbose=True)

        if "pubmed" in sources:
            if run_manager:
                await run_manager.on_text(f"开始检索PubMed医学文献: '{query_to_use}'...\n", verbose=True)
            try:
                # --- 调用异步版本的 PubMed 获取方法 ---
                pubmed_results = await asyncio.to_thread(run_pubmed, query_to_use, num_results)

                if pubmed_results:
                    all_results.extend(pubmed_results)
                    if run_manager:
                        await run_manager.on_text(f"✅ 已从 PubMed获取{len(pubmed_results)}篇相关文献\n", verbose=True)
                else:
                     if run_manager:
                        await run_manager.on_text(f"⚠️ 未从PubMed找到与'{query_to_use}'相关的结果\n", verbose=True)

            except Exception as e:
                error_msg = f"PubMed搜索出错: {str(e)}"
                logger.error(error_msg, exc_info=True)
                if run_manager:
                    await run_manager.on_text(f"❌ {error_msg}\n", verbose=True)

        # ... 处理其他来源 ...

        # 构建最终结果 (与 _run 类似，但使用 await on_text)
        if not all_results:
            return f"未找到与'{original_query}' (英文查询: '{query_to_use}')相关的医学文献摘要。"

        if run_manager:
            await run_manager.on_text(f"📊 医学文献搜索完成，共找到{len(all_results)}篇相关文献\n", verbose=True)

        markdown = f"## 医学文献搜索结果\n\n"
        if has_chinese and original_query != query_to_use:
            markdown += f"**原始查询**: {original_query}\n"
            markdown += f"**英文查询**: {query_to_use}\n\n"
        else:
            markdown += f"**查询**: {query_to_use}\n\n"
        
        markdown += f"**结果数量**: {len(all_results)} 篇\n\n"

        if len(all_results) > 0:
            markdown += "## 文献列表\n\n"
            # --- > 修正 Markdown 格式化: 使用字典键访问 < ---
            for i, result_dict in enumerate(all_results, 1): # 重命名循环变量为 result_dict
                title = result_dict.get('title', 'N/A') # 使用 .get() 更安全
                pmid = result_dict.get('pmid', 'N/A')
                url = result_dict.get('url', '#')
                abstract = result_dict.get('abstract', 'N/A')
                markdown += f"### {i}. {title}\n" # 正确访问 title
                markdown += f"**PMID**: {pmid} | [查看原文]({url})\n\n"
                markdown += f"**摘要**:\n{abstract}\n\n"
                markdown += "---\n\n"

        return markdown

    # --- 需要将 PubMed 获取逻辑也改为异步 ---
    async def _fetch_pubmed_abstracts_async(
        self,
        query: str,
        num_results: int = 5,
        max_page: int = 10,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> List[PubMedResult]:
        logger.debug(f"[调试] _fetch_pubmed_abstracts_async: query={query}, num_results={num_results}")
        encoded_query = quote_plus(query)
        results = []
        page = 1
        base_url = "https://pubmed.ncbi.nlm.nih.gov/"

        # --- > 注意：httpx.AsyncClient 的 headers 是在创建时设置的 < ---
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=20.0, follow_redirects=True) as client:
             while len(results) < num_results and page <= max_page:
                if run_manager:
                    await run_manager.on_text(f"正在搜索PubMed第{page}页...\n", verbose=True)

                search_url = f"{base_url}?term={encoded_query}&page={page}"
                current_headers = BROWSER_HEADERS.copy() # 复制基础 headers
                # --- > 为搜索页设置 Referer (可选) < ---
                if page > 1:
                    current_headers['Referer'] = f"{base_url}?term={encoded_query}&page={page-1}"
                # --- > 设置结束 < ---

                try:
                    # --- > 传递本次请求的 headers (如果需要动态修改的话) < ---
                    response = await client.get(search_url, headers=current_headers)
                    response.raise_for_status()
                    data = response.text

                    pat1_content_url = '<div class="docsum-wrap">.*?<.*?href="(.*?)".*?</a>'
                    content_url = re.compile(pat1_content_url, re.S).findall(data)

                    if not content_url: break

                    # --- > 在处理文章前稍作延时 < ---
                    await asyncio.sleep(0.5) # 暂停 0.5 秒
                    # --- > 延时结束 < ---

                    for idx, article_url_path in enumerate(content_url):
                        if len(results) >= num_results: break
                        full_url = base_url.rstrip('/') + article_url_path

                        # --- > 为文章页设置 Referer 为搜索结果页 < ---
                        article_headers = BROWSER_HEADERS.copy()
                        article_headers['Referer'] = search_url
                        # --- > 设置结束 < ---

                        if run_manager and idx % 3 == 0:
                            await run_manager.on_text(f"正在获取文献 {len(results)+1}/{num_results}...\n", verbose=True)

                        try:
                            # --- > 请求间的小延时 < ---
                            if idx > 0: await asyncio.sleep(0.2) # 每篇文章之间暂停 0.2 秒
                            # --- > 延时结束 < ---

                            # --- > 传递本次请求的 headers < ---
                            article_response = await client.get(full_url, headers=article_headers)
                            article_response.raise_for_status()
                            article_data = article_response.text

                            # --- > 提取 PMID, Title, Abstract < ---
                            pmid_match = re.search(r'/([0-9]+)/?', article_url_path)
                            pmid = pmid_match.group(1) if pmid_match else None
                            if not pmid: continue

                            soup = BeautifulSoup(article_data, 'html.parser')
                            title_tag = soup.select_one('h1.heading-title')
                            title = title_tag.get_text(strip=True) if title_tag else "标题未找到"

                            abstract_div = soup.select_one('.abstract-content.selected')
                            if not abstract_div:
                                abstract_div = soup.select_one('.abstract-content')

                            abstract = abstract_div.get_text(strip=True) if abstract_div else "摘要未找到"
                            abstract_found = bool(abstract and abstract != "摘要未找到")
                            # --- > 提取结束 < ---

                            if abstract_found:
                                results.append(PubMedResult(pmid=pmid, title=title, abstract=abstract, url=full_url))
                                if run_manager:
                                    await run_manager.on_text(f"✓ 已获取: {title[:40]}...\n", verbose=True)

                        except httpx.HTTPStatusError as http_err:
                             logger.error(f"获取文章详情 HTTP 错误 {http_err.response.status_code} for {full_url}: {http_err}")
                             if run_manager: await run_manager.on_text(f"获取文章 {pmid} 详情失败 (HTTP {http_err.response.status_code})，继续\n", verbose=True)
                        except Exception as err:
                            logger.error(f"处理PubMed文章 {full_url} 时出现错误: {err}", exc_info=True)
                            if run_manager: await run_manager.on_text(f"获取文章详情失败，继续尝试下一篇\n", verbose=True)

                    page += 1
                    # --- > 翻页前稍作延时 < ---
                    await asyncio.sleep(1.0) # 暂停 1 秒
                    # --- > 延时结束 < ---

                except httpx.RequestError as req_err:
                    logger.error(f"请求PubMed第{page}页时出错: {req_err}")
                    if run_manager: await run_manager.on_text(f"搜索PubMed第{page}页请求出错，尝试下一页\n", verbose=True)
                    page += 1
                    await asyncio.sleep(2.0) # 出错后等待时间长一点
                except Exception as err:
                    logger.error(f"处理PubMed第{page}页时出现未知错误: {err}", exc_info=True)
                    if run_manager: await run_manager.on_text(f"搜索PubMed第{page}页出错，尝试下一页\n", verbose=True)
                    page += 1
                    await asyncio.sleep(2.0) # 出错后等待时间长一点
        return results


# 创建工具实例
FastAbstractTool = create_logged_tool(FastAbstractTool)
fast_abstract_tool = FastAbstractTool()
