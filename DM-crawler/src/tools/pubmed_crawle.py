# src/tools/pubmed_sync_crawler_minimal.py (或者放在 fast_abstract_tool.py 里)

import requests
import re
import logging
from bs4 import BeautifulSoup
from typing import List, Dict
import time # 仍然建议保留延时

logger = logging.getLogger(__name__)

def run_pubmed(query: str, num_results: int) -> List[Dict[str, str]]:
    """
    同步执行 PubMed 爬取，严格遵循原脚本逻辑，仅修改输入输出。

    Args:
        query: 搜索关键词 (原 key)。
        num_results: 需要获取的文章数量 (原 num)。

    Returns:
        包含 pmid, title, abstract, url 的字典列表。
    """
    logger.info(f"开始 PubMed 爬取: query='{query}', num_results={num_results}")
    collected_results = [] # 用于存储结果

    # --- 原 PubMed.py 逻辑开始 (输入部分被替换) ---
    key = query # 使用参数 query
    # local_folder 被移除
    # num 使用参数 num_results

    # 尝试获取总结果数 (可选，保持原样)
    try:
        turl = "https://pubmed.ncbi.nlm.nih.gov/"
        # 注意：原脚本的第一次请求没有加 headers，这里也保持一致
        tdata = requests.get(turl, params={"term": key}, timeout=10).text # 增加超时
        pat_alldocu = '<span class="value">(.*?)</span>'
        alldocu = re.compile(pat_alldocu, re.S).findall(tdata)
        total_results_str = alldocu[0] if alldocu else "未知"
        logger.info(f"PubMed 搜索 '{key}' 发现约 {total_results_str} 个结果。")
    except Exception as e:
        logger.warning(f"获取总结果数失败: {e}")
        # 原脚本没有在这里处理错误，继续执行

    num = num_results # 使用参数 num_results

    downloaded_count = 0
    max_page = 50
    page = 1

    while downloaded_count < num and page <= max_page:
        url = f"https://pubmed.ncbi.nlm.nih.gov/?term={key}&page={page}"
        logger.debug(f"正在处理第{page}页: {url}") # print -> logger.debug
        try:
            # 注意：获取列表页的请求也没有加 headers，保持一致
            data = requests.get(url, timeout=20).text # 增加超时
        except requests.exceptions.RequestException as page_err:
             logger.error(f"获取列表页 {page} 失败: {page_err}")
             page += 1 # 跳过此页
             time.sleep(1) # 失败后稍等
             continue

        pat1_content_url = '<div class="docsum-wrap">.*?<.*?href="(.*?)".*?</a>'
        content_url = re.compile(pat1_content_url, re.S).findall(data)

        if not content_url:
            logger.info(f"第{page}页没有找到文章链接，可能已到达最后一页") # print -> logger.info
            break

        # --- > 保持 hd 在循环内定义 < ---
        hd = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # --- > 定义结束 < ---

        for i in range(len(content_url)):
            if downloaded_count >= num:
                break

            if i > 0 and i % 5 == 0:
                logger.debug(f"当前进度: 已处理 {downloaded_count}/{num} 篇文章") # print -> logger.debug

            curl = "https://pubmed.ncbi.nlm.nih.gov" + content_url[i]
            try:
                # --- > 保持 requests.get(headers=hd) < ---
                cdata = requests.get(curl, headers=hd, timeout=20).text # 增加超时
                # --- > 保持结束 < ---

                pmid_match = re.search(r'\/(\d+)\/*$', content_url[i])
                if pmid_match:
                    pmid = pmid_match.group(1)
                else:
                    logger.warning(f"无法从 {content_url[i]} 提取 PMID，跳过。")
                    continue

                pat3_content = '<div class="abstract-content selected".*?>(.*?)</div>'
                content_html = re.compile(pat3_content, re.S).findall(cdata)

                content_text = ""
                if not content_html:
                    # logger.info(f"文章 {pmid} 没有找到摘要内容，尝试其他方式提取") # print -> logger.info
                    soup = BeautifulSoup(cdata, 'html.parser')
                    abstract_div = soup.select_one('.abstract-content')
                    if abstract_div:
                        content_text = abstract_div.get_text(strip=True)
                    else:
                        # logger.info(f"文章 {pmid} 可能没有摘要，跳过") # print -> logger.info
                        content_text = "摘要未找到" # 标记为未找到，但仍然收集
                        # continue # 原脚本是跳过，这里改为收集并标记
                else:
                    soup = BeautifulSoup(content_html[0], 'html.parser')
                    content_text = soup.get_text(strip=True)

                # --- > 提取 Title (原脚本没有，但通常需要) < ---
                soup_title = BeautifulSoup(cdata, 'html.parser')
                title_tag = soup_title.select_one('h1.heading-title')
                title = title_tag.get_text(strip=True) if title_tag else "标题未找到"
                # --- > 提取结束 < ---

                # --- > 收集结果，替换文件写入 < ---
                collected_results.append({
                    "pmid": pmid,
                    "title": title, # 添加标题
                    "abstract": content_text,
                    "url": curl
                })
                # --- > 收集结束 < ---
                downloaded_count += 1

            except Exception as err:
                logger.error(f"处理文章 {curl} 时出现错误: {err}") # print -> logger.error
                continue # 保持原脚本逻辑：出错时继续

        page += 1
        time.sleep(0.5) # 建议在翻页前稍作停顿

    # --- > 返回收集到的结果列表 < ---
    logger.info(f" PubMed 爬取完成，共收集 {downloaded_count} 篇文章信息。")
    return collected_results
    # --- > 返回结束 < ---

# 用于独立测试
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.DEBUG)
#     test_query = "coronary heart disease"
#     test_num = 3
#     results = run_pubmed_sync_minimal(test_query, test_num)
#     print("\n--- Collected Results ---")
#     for res in results:
#         print(res)