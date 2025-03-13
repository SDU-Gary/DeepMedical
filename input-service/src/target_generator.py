#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
目标生成器模块 - 输入处理微服务的一部分
负责目标池检索和DeepSearch生成功能
"""

import json
import logging
import os
import re
import hashlib
import time
import asyncio
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from urllib.parse import urlparse, quote_plus
import sys
from concurrent.futures import ThreadPoolExecutor

# 将libs目录添加到系统路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'libs'))

# 尝试导入DeepSeek客户端
try:
    from deepseek_client.api_wrapper import DeepSeekAPI
except ImportError:
    # 创建一个模拟的DeepSeek API类
    class DeepSeekAPI:
        def __init__(self, api_key=None, endpoint=None):
            self.api_key = api_key
            self.endpoint = endpoint
            logging.warning("使用模拟的DeepSeek API客户端，请安装真实客户端")
        
        def chat(self, prompt, system_prompt=None, temperature=0.7):
            logging.info(f"模拟调用DeepSeek API: {prompt[:50]}...")
            # 返回模拟的成功响应
            if "生成URL" in prompt:
                return json.dumps([
                    "https://www.nejm.org/doi/full/10.1056/NEJMoa2310158",
                    "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(23)00814-2/fulltext",
                    "https://jamanetwork.com/journals/jama/fullarticle/2810006",
                    "https://www.nature.com/articles/s41591-023-02356-",
                    "https://academic.oup.com/eurheartj/article/44/20/1876/7079922"
                ], ensure_ascii=False)
            return ""

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
DEEPSEEK_API = DeepSeekAPI()

# 目标池相关配置
TARGET_POOL_DIR = Path(__file__).parent.parent / 'data' / 'targets'
INDEX_DIR = Path(__file__).parent.parent / 'data' / 'index'
MAX_RECORDS_PER_FILE = 1000

# 初始化目录
def init_directories():
    """初始化目标池目录结构"""
    TARGET_POOL_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

# 调用初始化函数
init_directories()

def get_part_files() -> List[Path]:
    """获取所有分片文件路径"""
    return sorted(TARGET_POOL_DIR.glob('part*.json'))

def find_last_part_file() -> Path:
    """找到最后一个分片文件"""
    part_files = get_part_files()
    
    if not part_files:
        # 如果没有分片文件，创建第一个
        new_file = TARGET_POOL_DIR / 'part1.json'
        with open(new_file, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False)
        return new_file
    
    return part_files[-1]

def create_new_part(data: Dict = None) -> Path:
    """创建新的分片文件"""
    part_files = get_part_files()
    
    if not part_files:
        new_part_num = 1
    else:
        # 从最后一个文件名提取编号
        last_file = part_files[-1].name
        last_part_num = int(re.search(r'part(\d+)', last_file).group(1))
        new_part_num = last_part_num + 1
    
    new_file = TARGET_POOL_DIR / f'part{new_part_num}.json'
    
    if data:
        with open(new_file, 'w', encoding='utf-8') as f:
            json.dump([data], f, ensure_ascii=False, indent=2)
    else:
        with open(new_file, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False)
    
    return new_file

def load_all_targets() -> List[Dict]:
    """加载所有目标数据"""
    all_targets = []
    part_files = get_part_files()
    
    for file_path in part_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                targets = json.load(f)
                all_targets.extend(targets)
        except Exception as e:
            logger.error(f"加载目标文件失败 {file_path}: {e}")
    
    return all_targets

def url_exists_in_pool(url: str) -> bool:
    """检查URL是否已存在于目标池中"""
    # 首先尝试使用索引快速检查
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    index_file = os.path.join(INDEX_DIR, "url_index.json")
    
    if os.path.exists(index_file):
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                url_index = json.load(f)
                if url_hash in url_index:
                    return True
        except Exception as e:
            logger.warning(f"读取URL索引文件失败: {e}")
    
    # 如果没有索引或者索引没有命中，可能是索引没有及时更新
    # 做全量扫描检查
    for file_path in get_part_files():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                targets = json.load(f)
                if any(target.get('url') == url for target in targets):
                    logger.info(f"URL重复检测: {url} 已存在于 {file_path}")
                    return True
        except Exception as e:
            logger.error(f"检查URL重复时加载目标文件失败 {file_path}: {e}")
    
    # 没有找到重复
    return False

def append_target(new_data: Dict) -> bool:
    """添加新的目标到池中，并进行去重"""
    # 检查URL是否已存在
    url = new_data.get('url')
    if not url:
        logger.error("无效的目标数据: 缺少URL")
        return False
    
    # 检查URL是否已存在
    if url_exists_in_pool(url):
        logger.info(f"去重: URL {url} 已存在于目标池中，已跳过")
        return False
    
    # 生成唯一ID
    if 'id' not in new_data:
        new_data['id'] = generate_target_id(url)
    
    # 添加时间戳
    if 'created_at' not in new_data:
        new_data['created_at'] = datetime.now().isoformat()
    
    # 找到最后一个未满的分片文件
    latest_file = find_last_part_file()
    
    try:
        with open(latest_file, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            if len(data) >= MAX_RECORDS_PER_FILE:
                # 创建新分片
                create_new_part(new_data)
            else:
                # 添加到现有分片
                data.append(new_data)
                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.truncate()
        
        # 更新索引 - 包括URL索引
        update_indexes(new_data)
        
        logger.info(f"新目标已添加到池中: {url}")
        return True
    except Exception as e:
        logger.error(f"添加目标失败: {e}")
        return False

def generate_target_id(url: str) -> str:
    """基于URL生成目标ID"""
    hash_object = hashlib.md5(url.encode())
    hash_hex = hash_object.hexdigest()
    
    # 生成格式: <时间戳>-<hash前8位>
    timestamp = int(time.time())
    return f"{timestamp}-{hash_hex[:8]}"

def update_indexes(target: Dict):
    """更新索引文件"""
    # 更新关键词索引
    keyword_index_file = INDEX_DIR / 'keyword_index.json'
    try:
        if keyword_index_file.exists():
            with open(keyword_index_file, 'r', encoding='utf-8') as f:
                keyword_index = json.load(f)
        else:
            keyword_index = {}
        
        # 对每个关键词更新索引
        for keyword in target.get('keywords', []):
            if keyword in keyword_index:
                if target['id'] not in keyword_index[keyword]:
                    keyword_index[keyword].append(target['id'])
            else:
                keyword_index[keyword] = [target['id']]
        
        # 保存更新后的索引
        with open(keyword_index_file, 'w', encoding='utf-8') as f:
            json.dump(keyword_index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"更新关键词索引失败: {e}")
    
    # 更新域名索引
    domain_index_file = INDEX_DIR / 'domain_index.json'
    try:
        if domain_index_file.exists():
            with open(domain_index_file, 'r', encoding='utf-8') as f:
                domain_index = json.load(f)
        else:
            domain_index = {}
        
        # 提取域名
        domain = urlparse(target['url']).netloc
        
        if domain in domain_index:
            if target['id'] not in domain_index[domain]:
                domain_index[domain].append(target['id'])
        else:
            domain_index[domain] = [target['id']]
        
        # 保存更新后的索引
        with open(domain_index_file, 'w', encoding='utf-8') as f:
            json.dump(domain_index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"更新域名索引失败: {e}")
        
    # 更新URL索引 - 用于快速去重
    url_index_file = os.path.join(INDEX_DIR, "url_index.json")
    try:
        # 被索引的URL
        url = target.get('url')
        if not url:
            return
            
        # 生成URL的哈希值
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # 加载或创建索引
        if os.path.exists(url_index_file):
            try:
                with open(url_index_file, 'r', encoding='utf-8') as f:
                    url_index = json.load(f)
            except json.JSONDecodeError:
                # 如果文件损坏，创建新索引
                logger.warning("索引文件损坏，创建新索引")
                url_index = {}
        else:
            url_index = {}
        
        # 添加新URL的索引
        url_index[url_hash] = {
            "url": url,
            "id": target.get('id'),
            "created_at": target.get('created_at'),
            "source": target.get('source', 'unknown')
        }
        
        # 保存更新后的索引
        with open(url_index_file, 'w', encoding='utf-8') as f:
            json.dump(url_index, f, ensure_ascii=False, indent=2)
            
        logger.debug(f"URL索引已更新: {url} -> {url_hash}")
    except Exception as e:
        logger.error(f"更新URL索引失败: {e}")

# 查询与搜索相关函数
def query_by_keywords(keywords: List[str], limit: int = 10) -> List[Dict]:
    """通过关键词查询目标"""
    matched_ids = set()
    all_targets = load_all_targets()
    
    # 尝试从索引中优先查询
    keyword_index_file = INDEX_DIR / 'keyword_index.json'
    if keyword_index_file.exists():
        try:
            with open(keyword_index_file, 'r', encoding='utf-8') as f:
                keyword_index = json.load(f)
            
            # 对每个关键词查询相关目标ID
            for keyword in keywords:
                if keyword in keyword_index:
                    matched_ids.update(keyword_index[keyword])
        except Exception as e:
            logger.error(f"从索引查询关键词失败: {e}")
    
    # 如果索引中没有数据，或不存在索引，则进行全文扫描
    if not matched_ids:
        for target in all_targets:
            # 检查目标关键词是否匹配
            for keyword in keywords:
                target_keywords = target.get('keywords', [])
                if keyword.lower() in [k.lower() for k in target_keywords]:
                    matched_ids.add(target['id'])
                    break
    
    # 取出匹配到的目标
    result = []
    for target in all_targets:
        if target['id'] in matched_ids:
            result.append(target)
            if len(result) >= limit:
                break
    
    return result

def query_by_url_pattern(pattern: str, limit: int = 10) -> List[Dict]:
    """通过URL模式查询目标"""
    all_targets = load_all_targets()
    result = []
    
    for target in all_targets:
        if re.search(pattern, target['url'], re.IGNORECASE):
            result.append(target)
            if len(result) >= limit:
                break
    
    return result

def query_by_domain(domain: str, limit: int = 10) -> List[Dict]:
    """通过域名查询目标"""
    matched_ids = set()
    all_targets = load_all_targets()
    
    # 从域名索引中查询
    domain_index_file = INDEX_DIR / 'domain_index.json'
    if domain_index_file.exists():
        try:
            with open(domain_index_file, 'r', encoding='utf-8') as f:
                domain_index = json.load(f)
            
            if domain in domain_index:
                matched_ids.update(domain_index[domain])
        except Exception as e:
            logger.error(f"从索引查询域名失败: {e}")
    
    # 如果索引中没有数据，则进行扫描
    if not matched_ids:
        for target in all_targets:
            target_domain = urlparse(target['url']).netloc
            if domain.lower() in target_domain.lower():
                matched_ids.add(target['id'])
    
    # 取出匹配到的目标
    result = []
    for target in all_targets:
        if target['id'] in matched_ids:
            result.append(target)
            if len(result) >= limit:
                break
    
    return result

# 定义搜索引擎配置
SEARCH_ENGINES = {
    "google": {
        "search_url": "https://www.google.com/search?q={query}&num=10",
        "result_selector": "div.yuRUbf > a",
        "weight": 1.0,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    },
    "bing": {
        "search_url": "https://www.bing.com/search?q={query}&count=10",
        "result_selector": "li.b_algo h2 > a",
        "weight": 0.8,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    },
    "pubmed": {
        "search_url": "https://pubmed.ncbi.nlm.nih.gov/?term={query}&size=10",
        "result_selector": "article.full-docsum > div.docsum-wrap > div.docsum-content > a.docsum-title",
        "weight": 1.2,  # 医学搜索赋予更高权重
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    },
    "scholar": {
        "search_url": "https://scholar.google.com/scholar?q={query}&hl=en&num=10",
        "result_selector": "h3.gs_rt > a",
        "weight": 1.1,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
}

async def fetch_search_results(engine_name: str, query: str) -> List[str]:
    """从指定搜索引擎获取搜索结果
    
    Args:
        engine_name: 搜索引擎名称
        query: 搜索查询词
        
    Returns:
        URL列表
    """
    # 开发模式下返回模拟数据
    if DEV_MODE:
        logger.info(f"开发模式: 为{engine_name}返回模拟搜索结果")
        # 为不同搜索引擎生成不同的模拟数据
        if engine_name == "google":
            return [
                "https://www.nejm.org/doi/full/10.1056/NEJMoa2310158",
                "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(23)00814-2/fulltext",
                "https://jamanetwork.com/journals/jama/fullarticle/2810006"
            ]
        elif engine_name == "bing":
            return [
                "https://www.nature.com/articles/s41591-023-02356-1",
                "https://academic.oup.com/eurheartj/article/44/20/1876/7079922",
                "https://www.ahajournals.org/doi/10.1161/CIRCULATIONAHA.123.064579"
            ]
        elif engine_name == "pubmed":
            return [
                "https://pubmed.ncbi.nlm.nih.gov/36938644/",
                "https://pubmed.ncbi.nlm.nih.gov/35443107/",
                "https://pubmed.ncbi.nlm.nih.gov/34449181/"
            ]
        elif engine_name == "scholar":
            return [
                "https://www.sciencedirect.com/science/article/pii/S0735109723073608",
                "https://heart.bmj.com/content/109/17/1311",
                "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8830475/"
            ]
        # 其他引擎返回通用结果
        return [
            "https://www.nejm.org/doi/full/10.1056/NEJMra2210632",
            "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/Chronic-Coronary-Syndromes"
        ]
        
    # 生产模式下的实际搜索逻辑
    engine_config = SEARCH_ENGINES.get(engine_name)
    if not engine_config:
        logger.error(f"未知的搜索引擎: {engine_name}")
        return []
    
    # 备用方法：如果beautifulsoup不可用，使用正则表达式提取URL
    def extract_urls_with_regex(html_content, base_url):
        pattern = r'href=[\'"]?([^\'" >]+)'
        urls = re.findall(pattern, html_content)
        valid_urls = []
        for url in urls:
            # 过滤JavaScript和内部链接
            if url.startswith('http') and not url.startswith('javascript:'):
                valid_urls.append(url)
            elif url.startswith('/') and not url.startswith('javascript:'):
                # 相对URL转为绝对URL
                valid_urls.append(f"{base_url}{url}")
        return valid_urls
    
    try:
        # 准备请求参数
        encoded_query = quote_plus(query)
        search_url = engine_config["search_url"].format(query=encoded_query)
        headers = {"User-Agent": engine_config["user_agent"]}
        
        # 异步执行HTTP请求
        # 由于requests库不支持原生的异步，我们使用线程池来模拟异步行为
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: requests.get(search_url, headers=headers, timeout=10)
        )
        
        if response.status_code != 200:
            logger.warning(f"{engine_name}搜索请求失败: HTTP {response.status_code}")
            return []
        
        # 获取HTML内容
        html_content = response.text
        
        # 尝试使用BeautifulSoup解析HTML（如果可用）
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            result_links = soup.select(engine_config["result_selector"])
            
            urls = []
            for link in result_links:
                href = link.get('href')
                if href and href.startswith('http'):
                    urls.append(href)
            
            logger.info(f"{engine_name}返回了{len(urls)}个结果")
            return urls
        except ImportError:
            # 如果BeautifulSoup不可用，使用正则表达式提取
            logger.warning("BeautifulSoup不可用，使用正则表达式提取URL")
            base_url = f"{response.url.split('://', 1)[0]}://{urlparse(response.url).netloc}"
            urls = extract_urls_with_regex(html_content, base_url)
            
            # 简单过滤，保留前10个结果
            filtered_urls = []
            for url in urls:
                if len(filtered_urls) >= 10:
                    break
                # 避免搜索引擎内部链接
                if not any(se in url for se in ["google", "bing", "search", "scholar.google"]):
                    filtered_urls.append(url)
            
            logger.info(f"{engine_name}返回了{len(filtered_urls)}个结果 (使用正则表达式)")
            return filtered_urls
            
    except Exception as e:
        logger.error(f"{engine_name}搜索出错: {e}")
        return []

async def generate_medical_urls(query: str, intent_data: Dict) -> List[str]:
    """通过调用多个搜索引擎生成医学领域的URL列表"""
    # 从意图分析中提取相关信息
    intent_class = intent_data.get('intent_analysis', {}).get('intent_class', '')
    key_terms = intent_data.get('intent_analysis', {}).get('key_terms', [])
    
    # 根据意图类别选择搜索引擎
    engines_to_use = []
    
    if intent_class == "学术研究":
        # 学术研究优先使用学术搜索引擎
        engines_to_use = ["pubmed", "scholar", "google"]
    elif intent_class == "临床决策":
        # 临床决策使用医学专业和综合搜索引擎
        engines_to_use = ["pubmed", "google", "bing"]
    else:  # 商业需求或其他
        # 一般信息使用通用搜索引擎
        engines_to_use = ["google", "bing", "pubmed"]
    
    # 构建增强搜索查询
    enhanced_query = query
    if key_terms:
        # 将关键词添加到查询中以增强搜索相关性
        medical_terms = " ".join([term for term in key_terms if len(term) > 1])
        enhanced_query = f"{query} {medical_terms}"
    
    # 如果是医学专业查询，添加医学术语
    if intent_class in ["学术研究", "临床决策"]:
        enhanced_query = f"{enhanced_query} medical research journal article"
    
    logger.info(f"使用增强查询: {enhanced_query}")
    logger.info(f"将查询以下搜索引擎: {', '.join(engines_to_use)}")
    
    # 并行调用多个搜索引擎
    tasks = [fetch_search_results(engine, enhanced_query) for engine in engines_to_use]
    results = await asyncio.gather(*tasks)
    
    # 合并结果并去重
    all_urls = []
    url_sources = {}  # 记录URL来源的搜索引擎
    
    for i, engine_results in enumerate(results):
        engine_name = engines_to_use[i]
        engine_weight = SEARCH_ENGINES[engine_name]["weight"]
        
        for url in engine_results:
            if url in url_sources:
                # URL已存在，增加其权重得分
                url_sources[url]["count"] += 1
                url_sources[url]["weight"] += engine_weight
            else:
                # 新URL
                url_sources[url] = {
                    "count": 1,
                    "weight": engine_weight,
                    "engines": [engine_name]
                }
                all_urls.append(url)
    
    # 基于权重对结果排序
    sorted_urls = sorted(all_urls, key=lambda url: url_sources[url]["weight"], reverse=True)
    
    # 限制结果数量并返回
    result_limit = 10
    final_urls = sorted_urls[:result_limit]
    
    logger.info(f"集成搜索共返回{len(final_urls)}个结果")
    
    # 如果没有找到结果，返回默认的医学网站URL
    if not final_urls:
        logger.warning("未找到搜索结果，返回默认医学网站")
        return [
            "https://pubmed.ncbi.nlm.nih.gov/",
            "https://www.nejm.org/",
            "https://www.thelancet.com/",
            "https://jamanetwork.com/",
            "https://www.bmj.com/"
        ]
    
    return final_urls

async def process_user_input(user_input: str, intent_data: Dict) -> Dict:
    """处理用户输入，生成目标URL列表"""
    result = {
        "raw_input": user_input,
        "intent_data": intent_data,
        "targets": [],
        "validation_info": {
            "detected_urls": [],
            "valid_urls": [],
            "invalid_urls": []
        }
    }
    
    # 导入URL验证器模块
    from pathlib import Path
    import sys
    sys.path.append(str(Path(__file__).parent))
    import url_validator
    
    # 提取输入中的URL
    detected_urls = url_validator.detect_url(user_input)
    result["validation_info"]["detected_urls"] = detected_urls.copy()
    
    if detected_urls:
        # 如果包含URL，使用完整的验证功能
        valid_urls = []
        invalid_urls = []
        
        # 对每个URL进行完整的异步验证
        for url in detected_urls:
            # 使用完整的validate_url函数进行验证，而不仅仅是语法验证
            validation_result = await url_validator.validate_url(url, user_input)
            
            if validation_result["valid"]:
                # 只有完全验证通过的URL才会添加到目标池
                url_data = {
                    "url": url,
                    "keywords": intent_data.get('intent_analysis', {}).get('key_terms', []),
                    "source": "user_input",
                    "relevance_score": validation_result.get("relevance_score", 1.0) or 1.0  # 用户直接提供的URL相关性默认最高
                }
                append_target(url_data)
                valid_urls.append(url_data)
                result["validation_info"]["valid_urls"].append(url)
            else:
                # 记录无效URL及其原因
                invalid_urls.append({
                    "url": url,
                    "reason": validation_result.get("reason", "未知原因")
                })
                result["validation_info"]["invalid_urls"].append({
                    "url": url,
                    "reason": validation_result.get("reason", "未知原因")
                })
        
        # 将有效URL添加到结果中
        result["targets"].extend(valid_urls)
        
        # 记录验证统计信息
        logger.info(f"用户输入中检测到{len(detected_urls)}个URL，其中{len(valid_urls)}个有效，{len(invalid_urls)}个无效")
    


    #------ 使用集成搜索引擎生成新的URL列表 ------
    generated_urls = await generate_medical_urls(user_input, intent_data)
    generated_targets = []
    
    # 对每个生成的URL进行完整验证
    valid_generated_count = 0
    
    for i, url in enumerate(generated_urls):
        # 首先进行完整的URL验证
        validation_result = await url_validator.validate_url(url, user_input)
        
        if validation_result["valid"]:
            # 只有验证通过的URL才会评分并添加到目标池
            # 计算相关性得分 - 排名越靠前得分越高
            relevance_score = 0.9 - (valid_generated_count * 0.05) if valid_generated_count < 10 else 0.4
            relevance_score = max(0.4, min(0.9, relevance_score))  # 限制在0.4-0.9范围内
            
            # 如果验证结果中有相关性得分，优先使用验证结果的得分
            if validation_result.get("relevance_score") is not None:
                relevance_score = validation_result["relevance_score"]
            
            url_data = {
                "url": url,
                "keywords": intent_data.get('intent_analysis', {}).get('key_terms', []),
                "source": "search_engine",
                "relevance_score": relevance_score
            }
            append_target(url_data)
            generated_targets.append(url_data)
            valid_generated_count += 1
            
            # 记录到验证信息中
            result["validation_info"]["valid_urls"].append(url)
        else:
            # 记录无效URL
            result["validation_info"]["invalid_urls"].append({
                "url": url,
                "reason": validation_result.get("reason", "生成的URL验证失败")
            })
    
    result["targets"].extend(generated_targets)
    result["total_targets"] = len(result["targets"])
    
    # 添加搜索引擎使用信息到结果中
    result["search_info"] = {
        "engines_used": [e for e in SEARCH_ENGINES.keys() if SEARCH_ENGINES[e]["weight"] > 0],
        "query": user_input,
        "timestamp": datetime.now().isoformat()
    }
    
    return result

# 入口函数
def get_targets(user_input: str, intent_data: Dict) -> Dict:
    """主要入口函数，处理用户输入并生成目标"""
    # 使用asyncio运行异步函数
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(process_user_input(user_input, intent_data))
    return result

# 新增强化版环境变量配置
def configure_api_from_env():
    """从环境变量配置API连接参数"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    endpoint = os.environ.get("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1")
    
    if api_key:
        global DEEPSEEK_API
        DEEPSEEK_API = DeepSeekAPI(api_key=api_key, endpoint=endpoint)
        logger.info(f"已配置DeepSeek API连接到端点: {endpoint}")

# 启动时配置环境
configure_api_from_env()

# 如果作为独立脚本运行，执行测试代码
if __name__ == "__main__":
    import sys
    from pprint import pprint
    
    # 导入意图分析器
    sys.path.append(str(Path(__file__).parent))
    import intent_analyzer
    
    if len(sys.argv) > 1:
        test_text = sys.argv[1]
    else:
        # 默认测试文本
        test_text = "我想查找最新的冠心病治疗方案，特别是PCI手术后的抗凝管理"
    
    # 分析意图
    intent_result = intent_analyzer.process_input(test_text)
    
    # 生成目标
    targets = get_targets(test_text, intent_result)
    
    # 打印结果
    print("生成的目标URL:")
    pprint(targets)
