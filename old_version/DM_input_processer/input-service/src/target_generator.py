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
import threading
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from urllib.parse import urlparse, quote_plus
import sys
from concurrent.futures import ThreadPoolExecutor

# 导入搜索引擎API
try:
    from googlesearch import search as google_search
    GOOGLE_SEARCH_AVAILABLE = True
except ImportError:
    GOOGLE_SEARCH_AVAILABLE = False
    logging.warning("无法导入googlesearch，Google搜索功能将不可用")

try:
    import arxiv
    ARXIV_SEARCH_AVAILABLE = True
except ImportError:
    ARXIV_SEARCH_AVAILABLE = False
    logging.warning("无法导入arxiv，学术论文搜索功能将不可用")
    
try:
    from langchain_community.tools import DuckDuckGoSearchResults, DuckDuckGoSearchRun
    DUCKDUCKGO_AVAILABLE = True
except ImportError:
    DUCKDUCKGO_AVAILABLE = False
    logging.warning("无法导入DuckDuckGo搜索工具，将使用备用搜索方法")

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
# 基础数据目录
DATA_DIR = Path(__file__).parent.parent / 'data'
# 目标池和索引目录
TARGET_POOL_DIR = DATA_DIR / 'targets'
INDEX_DIR = DATA_DIR / 'index'
MAX_RECORDS_PER_FILE = 1000

# 初始化目录
def init_directories():
    """初始化目标池目录结构"""
    try:
        TARGET_POOL_DIR.mkdir(parents=True, exist_ok=True)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        
        # 确保目录可写入
        test_file = TARGET_POOL_DIR / '.test_write'
        with open(test_file, 'w') as f:
            f.write('test')
        if test_file.exists():
            test_file.unlink()  # 删除测试文件
            
        # 初始化初始分片文件如果不存在
        part_files = list(TARGET_POOL_DIR.glob('part*.json'))
        if not part_files:
            initial_file = TARGET_POOL_DIR / 'part1.json'
            with open(initial_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)
            logger.info(f"创建初始目标文件: {initial_file}")
            
        # 初始化索引文件
        for index_name in ['url_index.json', 'keyword_index.json', 'domain_index.json']:
            index_file = INDEX_DIR / index_name
            if not index_file.exists():
                with open(index_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False)
                logger.info(f"创建索引文件: {index_file}")
        
        logger.info("目标池目录结构初始化成功")
        return True
    except Exception as e:
        logger.error(f"初始化目标池目录结构失败: {e}")
        return False

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
    # 确保目录结构已初始化
    if not os.path.exists(TARGET_POOL_DIR):
        logger.warning("目标池目录不存在，尝试重新初始化")
        if not init_directories():
            logger.error("无法初始化目标池目录，添加目标失败")
            return False
    
    # 检查URL是否存在且有效
    url = new_data.get('url')
    if not url:
        logger.error("无效的目标数据: 缺少URL")
        return False
    
    if not isinstance(url, str) or not url.startswith('http'):
        logger.error(f"无效的URL格式: {url}")
        return False
    
    # 检查URL是否已存在（去重）
    try:
        if url_exists_in_pool(url):
            logger.info(f"去重: URL {url} 已存在于目标池中，已跳过")
            return False
    except Exception as e:
        # 如果查重出错，记录日志但继续尝试添加
        logger.warning(f"检查URL重复时出错: {e}")
    
    # 生成唯一ID和时间戳
    try:
        if 'id' not in new_data:
            new_data['id'] = generate_target_id(url)
        
        if 'created_at' not in new_data:
            new_data['created_at'] = datetime.now().isoformat()
        
        # 确保关键字段存在且不为空
        if 'keywords' not in new_data or not new_data['keywords']:
            new_data['keywords'] = []
        
        if 'source' not in new_data:
            new_data['source'] = "search_engine"
        
        # 找到最后一个分片文件
        latest_file = find_last_part_file()
        
        # 确保分片文件存在且可读写
        if not os.path.exists(latest_file):
            logger.warning(f"目标池分片文件 {latest_file} 不存在，创建新的分片文件")
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)
        
        # 读取并更新目标文件
        with open(latest_file, 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
                
                # 确保数据是列表格式
                if not isinstance(data, list):
                    logger.warning(f"目标文件 {latest_file} 格式不正确，重置为空列表")
                    data = []
                
                if len(data) >= MAX_RECORDS_PER_FILE:
                    # 创建新分片
                    logger.info(f"当前分片文件 {latest_file} 已满，创建新分片")
                    new_file = create_new_part(new_data)
                    logger.info(f"成功创建新分片文件 {new_file} 并添加目标")
                else:
                    # 添加到现有分片
                    data.append(new_data)
                    f.seek(0)
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.truncate()
                    logger.info(f"成功将目标添加到分片文件 {latest_file}")
            except json.JSONDecodeError as e:
                logger.error(f"目标文件 {latest_file} JSON解析错误: {e}，重置并创建新文件")
                f.seek(0)
                f.truncate(0)
                json.dump([new_data], f, ensure_ascii=False, indent=2)
        
        # 更新索引
        try:
            update_indexes(new_data)
        except Exception as e:
            logger.warning(f"更新索引失败，但目标数据已保存: {e}")
        
        logger.info(f"新目标已成功添加到池中: {url}")
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
    # 更新URL索引
    url_index_file = INDEX_DIR / 'url_index.json'
    try:
        if url_index_file.exists():
            with open(url_index_file, 'r', encoding='utf-8') as f:
                url_index = json.load(f)
        else:
            url_index = {}
        
        # 将URL哈希添加到索引
        url = target.get('url')
        if url:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            url_index[url_hash] = target['id']
            
            # 保存更新后的URL索引
            with open(url_index_file, 'w', encoding='utf-8') as f:
                json.dump(url_index, f, ensure_ascii=False, indent=2)
            logger.info(f"已将URL {url} 添加到索引")
    except Exception as e:
        logger.error(f"更新URL索引失败: {e}")
    
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

# 定义标准的搜索结果类
class SearchResult:
    """统一的搜索结果数据结构，包含标题、URL、摘要等信息"""
    def __init__(
        self, 
        title: str, 
        url: str, 
        snippet: str, 
        source: str, 
        date: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None,
        target: Optional[str] = None
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.date = date
        self.metadata = metadata or {}
        self.target = target or url  # 默认使用URL作为target
    
    def to_dict(self) -> Dict[str, Any]:
        """将搜索结果转换为字典形式"""
        return {
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'source': self.source,
            'date': self.date,
            'metadata': self.metadata,
            'target': self.target
        }
    
    def __repr__(self) -> str:
        return f"SearchResult(title='{self.title[:30]}...', source='{self.source}', url='{self.url[:30]}...')"

# 搜索结果缓存类，提高性能并减少重复请求
class SearchCache:
    """搜索结果缓存，避免重复请求并提高性能"""
    def __init__(self, cache_dir: Optional[str] = None, ttl: int = 3600):
        self.cache_dir = cache_dir or os.path.join(DATA_DIR, 'search_cache')
        self.ttl = ttl  # 缓存有效期（秒）
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.info(f"搜索缓存初始化: {self.cache_dir}")
    
    def _get_cache_key(self, query: str, engine: str) -> str:
        """生成缓存键"""
        hash_key = hashlib.md5(f"{query}:{engine}".encode()).hexdigest()
        return hash_key
    
    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, query: str, engine: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存结果"""
        key = self._get_cache_key(query, engine)
        path = self._get_cache_path(key)
        
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查缓存是否过期
                if time.time() - data['timestamp'] <= self.ttl:
                    logger.info(f"使用缓存结果：{engine}引擎的查询'{query}'")
                    return data['results']
            except Exception as e:
                logger.error(f"读取缓存出错: {e}")
        
        return None
    
    def set(self, query: str, engine: str, results: List[Dict[str, Any]]):
        """缓存搜索结果"""
        try:
            key = self._get_cache_key(query, engine)
            path = self._get_cache_path(key)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': time.time(),
                    'results': results
                }, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已缓存 {engine} 引擎的 '{query}' 查询结果")
                
        except Exception as e:
            logger.error(f"缓存搜索结果出错: {e}")

# 初始化全局缓存对象
search_cache = SearchCache()

async def fetch_search_results(engine_name: str, query: str) -> List[str]:
    """从指定搜索引擎获取搜索结果
    
    Args:
        engine_name: 搜索引擎名称
        query: 搜索查询词
        
    Returns:
        URL列表
    """
    # 首先检查缓存
    cached_results = search_cache.get(query, engine_name)
    if cached_results is not None:
        return cached_results
        
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
    

    # 实际搜索处理
    try:
        # 准备请求参数并增强头信息
        encoded_query = quote_plus(query)
        search_url = engine_config["search_url"].format(query=encoded_query)
        
        # 使用更真实的请求头，模拟真实浏览器
        headers = {
            "User-Agent": engine_config["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        urls = []
        # 重试机制
        max_retries = 3
        retry_delay = 2  # 初始重试延迟（秒）
        
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试{engine_name}搜索 (第{attempt+1}次尝试): {search_url}")
                
                # 异步执行HTTP请求
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: requests.get(search_url, headers=headers, timeout=15)
                )
                
                if response.status_code != 200:
                    logger.warning(f"{engine_name}搜索请求失败: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        # 指数退避
                        wait_time = retry_delay * (2 ** attempt)
                        logger.info(f"等待{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return []
                
                # 获取并解码HTML内容
                html_content = response.text
                
                # 首先尝试使用BeautifulSoup解析
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 尝试多种选择器策略
                    selectors = [engine_config["result_selector"]]
                    
                    # 添加备用选择器
                    if engine_name == "google":
                        selectors.extend(["div.g div.yuRUbf > a", "div.tF2Cxc > div.yuRUbf > a", "a.l"])
                    elif engine_name == "bing":
                        selectors.extend(["#b_results li.b_algo h2 > a", "#b_results .b_title > a"])
                    elif engine_name == "pubmed":
                        selectors.extend(["article.docsum-wrap > a", ".docsum-title"])
                    elif engine_name == "scholar":
                        selectors.extend(["div.gs_ri h3 > a", ".gs_rt a"])
                    
                    # 尝试所有选择器直到找到结果
                    for selector in selectors:
                        result_links = soup.select(selector)
                        if result_links:
                            break
                    
                    # 解析链接
                    for link in result_links:
                        href = link.get('href')
                        # 确保链接有效并且是绝对URL
                        if href:
                            if not href.startswith('http'):
                                # 相对URL，转为绝对URL
                                base_url = f"{response.url.split('://', 1)[0]}://{urlparse(response.url).netloc}"
                                if href.startswith('/'):
                                    href = f"{base_url}{href}"
                                else:
                                    href = f"{base_url}/{href}"
                            
                            # 过滤掉搜索引擎内部链接
                            if not any(se in href.lower() for se in ["google.com/search", "bing.com/search", "scholar.google"]):
                                urls.append(href)
                    
                    # 如果使用BeautifulSoup没有找到结果，尝试使用正则表达式
                    if not urls:
                        logger.warning(f"{engine_name}选择器未找到结果，尝试使用正则表达式")
                        base_url = f"{response.url.split('://', 1)[0]}://{urlparse(response.url).netloc}"
                        urls = extract_urls_with_regex(html_content, base_url)
                    
                except ImportError:
                    # 如果BeautifulSoup不可用，使用正则表达式提取
                    logger.warning("BeautifulSoup不可用，使用正则表达式提取URL")
                    base_url = f"{response.url.split('://', 1)[0]}://{urlparse(response.url).netloc}"
                    urls = extract_urls_with_regex(html_content, base_url)
                
                # 过滤结果
                filtered_urls = []
                irrelevant_domains = [
                    "pinterest", "instagram", "facebook", "twitter", "youtube", "tiktok",
                    "reddit", "quora", "linkedin", "amazon.com", "ebay.com", "etsy.com"
                ]
                
                for url in urls:
                    # 跳过社交媒体和电商网站
                    if any(domain in url.lower() for domain in irrelevant_domains):
                        continue
                    
                    # 跳过搜索引擎自身的结果页
                    if any(se in url.lower() for se in ["google.com/search", "bing.com/search", "scholar.google"]):
                        continue
                        
                    filtered_urls.append(url)
                    if len(filtered_urls) >= 10:  # 限制结果数量
                        break
                
                # 记录结果
                if filtered_urls:
                    logger.info(f"{engine_name}返回了{len(filtered_urls)}个结果")
                    
                    # 缓存结果
                    search_cache.set(query, engine_name, filtered_urls)
                    return filtered_urls
                else:
                    logger.warning(f"{engine_name}未返回有效结果")
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.info(f"等待{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        return []
                        
            except Exception as e:
                logger.error(f"{engine_name}搜索第{attempt+1}次尝试失败: {e}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.info(f"等待{wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    # 所有重试都失败，返回空列表
                    return []
        
        # 如果最终没有找到结果，返回空列表
        return []
            
    except Exception as e:
        logger.error(f"{engine_name}搜索出错: {e}")
        return []

# 统一搜索器类，整合多个搜索引擎并提供可靠的搜索体验
class UnifiedSearcher:
    """统一搜索器类，整合多个搜索引擎的结果以提供更可靠的搜索体验"""
    
    # 类级别执行器以重用线程池
    _executor = None
    _executor_lock = None
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        max_results: int = 10,
        region: str = "wt-wt",
        safesearch: str = "moderate",
        timelimit: Optional[str] = None,
        backend: str = "news",
        cache_ttl: int = 3600,
        user_agent: Optional[str] = None,
        cache: Optional[SearchCache] = None
    ):
        """
        初始化搜索器
        
        Args:
            proxy: 代理服务器设置，如"http://user:pass@hostname:port"
            max_results: 最大返回结果数
            region: DuckDuckGo搜索区域设置
            safesearch: DuckDuckGo安全搜索级别
            timelimit: 搜索时间限制
            backend: DuckDuckGo后端类型
            cache_ttl: 缓存过期时间（秒）
            user_agent: 自定义User-Agent
            cache: 缓存对象，为空则使用默认缓存
        """
        self.max_results = max_results
        self.proxy = proxy
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
        self.logger = logger
        
        # 初始化DuckDuckGo搜索工具
        if DUCKDUCKGO_AVAILABLE:
            try:
                self.ddg_results = DuckDuckGoSearchResults(
                    backend=backend,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results
                )
                self.ddg_run = DuckDuckGoSearchRun()
                self.logger.info("初始化DuckDuckGo搜索工具成功")
            except Exception as e:
                self.logger.error(f"初始化DuckDuckGo搜索工具失败: {e}")
                self.ddg_results = None
                self.ddg_run = None
        else:
            self.ddg_results = None
            self.ddg_run = None
            self.logger.warning("无法加载DuckDuckGo搜索工具，将使用备用搜索方法")
            
        # 初始化缓存
        self.cache = cache or search_cache
        
        # 使用共享执行器以提高资源管理
        if not hasattr(UnifiedSearcher, '_executor'):
            UnifiedSearcher._executor_lock = threading.Lock()
            with UnifiedSearcher._executor_lock:
                if not hasattr(UnifiedSearcher, '_executor'):
                    UnifiedSearcher._executor = ThreadPoolExecutor(max_workers=6)
        
        self.executor = UnifiedSearcher._executor
        
        # 添加请求超时时间以避免挂起
        self.request_timeout = 10  # 10秒超时
    
    async def _search_arxiv(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行arXiv学术论文搜索"""
        if not ARXIV_SEARCH_AVAILABLE:
            self.logger.warning("arXiv搜索不可用，缺少arxiv库")
            return []

        results = []
        search_query = self._humanize_query(query)
        
        # 先检查缓存
        cached_results = self.cache.get(search_query, "arxiv")
        if cached_results:
            self.logger.info(f"使用arXiv搜索缓存结果: {search_query}")
            return [SearchResult(**r) for r in cached_results]
        
        try:
            # 执行arXiv搜索
            self.logger.info(f"执行arXiv搜索: {search_query}")
            
            # 使用arxiv库执行搜索
            loop = asyncio.get_event_loop()
            papers = await loop.run_in_executor(
                self.executor,
                lambda: list(arxiv.Search(
                    query=search_query,
                    max_results=num_results,
                    sort_by=arxiv.SortCriterion.Relevance
                ).results())
            )
            
            # 转换结果为SearchResult对象
            for paper in papers:
                full_summary = paper.summary
                
                # 创建更全面的摘要
                snippet = full_summary[:500] + "..." if len(full_summary) > 500 else full_summary
                
                # 获取PDF和摘要URL
                pdf_url = paper.pdf_url
                abstract_url = paper.entry_id.replace("http://", "https://") if paper.entry_id else pdf_url
                
                # 使用摘要URL作为主链接，更容易在浏览器中查看
                primary_url = abstract_url
                
                results.append(SearchResult(
                    title=paper.title,
                    url=primary_url,
                    snippet=snippet,
                    source="arXiv",
                    date=paper.published.strftime("%Y-%m-%d") if paper.published else None,
                    metadata={
                        "authors": [author.name for author in paper.authors],
                        "categories": paper.categories,
                        "type": "academic_paper",
                        "pdf_url": pdf_url,
                        "abstract_url": abstract_url,
                        "full_summary": full_summary,
                        "doi": paper.doi
                    }
                ))
            
            # 缓存结果
            if results:
                try:
                    # 确保我们存储的是字典，而不是SearchResult对象
                    result_dicts = []
                    for r in results:
                        if isinstance(r, SearchResult):
                            result_dicts.append(r.to_dict())
                        elif isinstance(r, dict):
                            result_dicts.append(r)
                        else:
                            self.logger.warning(f"跳过不可序列化的结果: {type(r)}")
                    
                    self.cache.set(search_query, "arxiv", result_dicts)
                except Exception as e:
                    self.logger.error(f"缓存arXiv搜索结果出错: {e}")
                
        except Exception as e:
            self.logger.error(f"arXiv搜索出错: {e}")
            
        return results
    
    async def _async_google_search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行Google搜索并处理结果"""
        results = []
        search_query = self._humanize_query(query)
        
        # 先检查缓存
        cached_results = self.cache.get(search_query, "google")

        '''
        if cached_results:
            self.logger.info(f"使用Google搜索缓存结果: {search_query}")
            return [SearchResult(**r) for r in cached_results]
        '''
            
        if not GOOGLE_SEARCH_AVAILABLE:
            self.logger.warning(f"Google搜索库不可用，尝试备用方法")
            try:
                # 使用备用方法
                raw_results = await fetch_search_results("google", search_query)
                for url in raw_results:
                    results.append(SearchResult(
                        title=url.split('/')[-1] if '/' in url else url,
                        url=url,
                        snippet="",
                        source="Google"
                    ))
                return results
            except Exception as e:
                self.logger.error(f"Google搜索备用方法失败: {e}")
                return []
        
        try:
            # 尝试最多3次搜索，以应对可能的网络问题
            for attempt in range(3):
                try:
                    self.logger.info(f"Google搜索尝试 {attempt+1}: {search_query}")
                    
                    # 使用googlesearch库执行搜索
                    loop = asyncio.get_event_loop()
                    search_results = await loop.run_in_executor(
                        self.executor,
                        lambda: list(google_search(
                            search_query, 
                            num_results=num_results * 2,  # 多获取一些，用于过滤
                            proxy=self.proxy,
                            timeout=self.request_timeout,
                            unique=True,
                            advanced=True  # 返回更详细的结果
                        ))
                    )
                    
                    # 处理搜索结果
                    filtered_results = []
                    irrelevant_domains = [
                        "pinterest", "instagram", "facebook", "twitter", 
                        "youtube", "tiktok", "reddit", "quora", "linkedin",
                        "msn.com/en-us/money", "msn.com/en-us/lifestyle",
                        "amazon.com", "ebay.com", "etsy.com", "walmart.com"
                    ]
                    
                    for result in search_results:
                        try:
                            # 检查结果类型并提取URL
                            if hasattr(result, 'url'):
                                # 如果是SearchResult对象
                                url = result.url
                                title = result.title if hasattr(result, 'title') else 'Untitled'
                                snippet = result.description if hasattr(result, 'description') else ''
                            elif isinstance(result, dict):
                                # 如果是字典
                                url = result.get('url', '')
                                title = result.get('title', result.get('url', 'Untitled'))
                                snippet = result.get('snippet', '')
                            else:
                                # 未知类型，跳过
                                self.logger.warning(f"无法处理的Google搜索结果类型: {type(result)}")
                                continue
                                
                            # 过滤掉不相关的域名
                            if url and isinstance(url, str) and any(domain in url.lower() for domain in irrelevant_domains):
                                continue
                                
                            filtered_results.append(
                                SearchResult(
                                    title=title,
                                    url=url,
                                    snippet=snippet,
                                    source="Google"
                                )
                            )
                        except Exception as e:
                            self.logger.error(f"处理Google搜索结果出错: {e}")
                            continue
                    
                    # 如果有结果，按照相关性评分排序
                    if filtered_results:
                        query_keywords = query.lower().split()
                        important_keywords = [word for word in query_keywords 
                                          if len(word) > 3 and word not in ["从", "与", "那个", "这个", "什么", "何时", "哪里", "哪个", "虽然"]]
                        
                        scored_results = []
                        for result in filtered_results:
                            score = 0
                            # 标题中的关键词得分更高
                            title_lower = result.title.lower() if result.title else ""
                            for keyword in important_keywords:
                                if keyword in title_lower:
                                    score += 3
                            
                            # 摘要中的关键词也计分
                            snippet_lower = result.snippet.lower() if result.snippet else ""
                            for keyword in important_keywords:
                                if keyword in snippet_lower:
                                    score += 1
                            
                            scored_results.append((score, result))
                        
                        # 按得分排序
                        scored_results.sort(reverse=True, key=lambda x: x[0])
                        results = [result for score, result in scored_results[:num_results]]
                    else:
                        results = []
                        for result in search_results[:num_results]:
                            try:
                                # 检查结果类型并提取字段
                                if hasattr(result, 'url'):
                                    # 如果是SearchResult对象
                                    url = result.url
                                    title = result.title if hasattr(result, 'title') else 'Untitled'
                                    snippet = result.description if hasattr(result, 'description') else ''
                                elif isinstance(result, dict):
                                    # 如果是字典
                                    url = result.get('url', '')
                                    title = result.get('title', result.get('url', 'Untitled'))
                                    snippet = result.get('snippet', '')
                                else:
                                    # 未知类型，跳过
                                    continue
                                    
                                results.append(SearchResult(
                                    title=title,
                                    url=url,
                                    snippet=snippet,
                                    source="Google"
                                ))
                            except Exception as e:
                                self.logger.error(f"转换Google搜索结果出错: {e}")
                    
                    break  # 搜索成功，跳出重试循环
                except Exception as e:
                    self.logger.error(f"Google搜索尝试 {attempt+1} 失败: {e}")
                    if attempt < 2:  # 如果不是最后一次尝试，等待后重试
                        await asyncio.sleep(2 ** attempt)  # 指数退避
            
            # 缓存结果
            if results:
                try:
                    # 确保我们存储的是字典，而不是SearchResult对象
                    result_dicts = [r.to_dict() for r in results]
                    self.cache.set(search_query, "google", result_dicts)
                except Exception as e:
                    self.logger.error(f"缓存Google搜索结果出错: {e}")
                
        except Exception as e:
            self.logger.error(f"Google搜索出错: {e}")
            
        return results
    
    def _humanize_query(self, query: str) -> str:
        """使搜索查询更加人性化，改善搜索结果质量"""
        # 去除多余的标点符号和格式化
        query = query.replace('?', ' ').replace('!', ' ').replace('"', ' ').replace("'", ' ')
        query = ' '.join(query.split())
        
        # 如果查询过长，截取重要部分
        if len(query) > 150:
            words = query.split()
            
            # 保留前5个词和后10个词来维持上下文
            if len(words) > 15:
                query = ' '.join(words[:5] + words[-10:])
            else:
                query = ' '.join(words[:15])
            
        return query
        
    async def _search_duckduckgo(self, query: str) -> List[SearchResult]:
        """执行DuckDuckGo搜索，使用缓存并处理错误"""
        # 先检查缓存
        cached_results = self.cache.get(query, "duckduckgo")
        if cached_results:
            self.logger.info(f"使用DuckDuckGo搜索缓存结果: {query}")
            return [SearchResult(**r) for r in cached_results]
        
        results = []
        
        # 使用LangChain的DuckDuckGo搜索工具
        try:
            if not self.ddg_results:
                self.logger.warning("DuckDuckGo搜索工具不可用，尝试替代方法")
                # 如果DDG工具不可用，尝试使用fetch_search_results
                raw_results = await fetch_search_results("bing", query)  # 使用Bing作为备用
                results = [
                    SearchResult(
                        title=url,
                        url=url,
                        snippet="",
                        source="DuckDuckGo (via Bing)"
                    ) for url in raw_results
                ]
            else:
                # 在线程池中执行以避免阻塞
                loop = asyncio.get_event_loop()
                try:
                    ddg_results_str = await loop.run_in_executor(
                        self.executor,
                        lambda: self.ddg_results.run(query)
                    )
                    
                    results.extend(self._parse_ddg_results(ddg_results_str))
                except Exception as e:
                    self.logger.error(f"DuckDuckGo搜索错误: {e}")
                    # 尝试使用更简单的DDG运行方法
                    if self.ddg_run:
                        try:
                            simple_result = await loop.run_in_executor(
                                self.executor,
                                lambda: self.ddg_run.run(query)
                            )
                            
                            results.append(
                                SearchResult(
                                    title="DuckDuckGo结果",
                                    url="",
                                    snippet=simple_result,
                                    source="DuckDuckGo"
                                )
                            )
                        except Exception as e:
                            self.logger.error(f"DuckDuckGo备用方法错误: {e}")
            
            # 缓存结果
            if results:
                try:
                    result_dicts = [r.to_dict() for r in results]
                    self.cache.set(query, "duckduckgo", result_dicts)
                except Exception as e:
                    self.logger.error(f"缓存DuckDuckGo搜索结果出错: {e}")
                
        except Exception as e:
            self.logger.error(f"DuckDuckGo搜索出错: {e}")
        
        return results
    
    def _parse_ddg_results(self, results_str: str) -> List[SearchResult]:
        """解析DuckDuckGo结果并改进错误处理"""
        results = []
        if not results_str or "snippet:" not in results_str:
            return results  # 如果输入无效，返回空列表
        
        entries = results_str.split("snippet:")
        for entry in entries[1:]:  # 跳过第一个空分割
            try:
                snippet_end = entry.find(", title:")
                title_end = entry.find(", link:")
                link_end = entry.find(", date:") if ", date:" in entry else entry.find(", source:") 
                date_end = entry.find(", source:") if ", date:" in entry else -1
                
                snippet = entry[:snippet_end].strip() if snippet_end > 0 else ""
                title = (entry[entry.find(", title:") + len(", title:"):title_end].strip() 
                        if title_end > snippet_end else "Untitled")
                link = (entry[entry.find(", link:") + len(", link:"):link_end].strip() 
                        if link_end > title_end else "")
                
                date = None
                if ", date:" in entry and date_end > link_end:
                    date = entry[entry.find(", date:") + len(", date:"):date_end].strip()
                
                results.append(SearchResult(
                    title=title,
                    url=link,
                    snippet=snippet,
                    source="DuckDuckGo",
                    date=date
                ))
            except Exception as e:
                self.logger.error(f"解析DuckDuckGo结果出错: {e}")
                continue
                
        return results
        
    async def _async_bing_search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行Bing搜索"""
        try:
            search_query = self._humanize_query(query)
            self.logger.info(f"执行Bing搜索: {search_query}")
            
            # 检查缓存
            cached_results = self.cache.get(search_query, "bing")
            if cached_results:
                self.logger.info(f"使用Bing搜索缓存结果: {search_query}")
                return [SearchResult(**r) for r in cached_results]
                
            # 开发模式下返回模拟数据
            if os.environ.get("DEV_MODE", "FALSE").lower() in ("true", "1", "yes"):
                self.logger.info(f"开发模式: 返回Bing模拟搜索结果")
            else:
                # 如果没有缓存，执行搜索
                raw_results = await fetch_search_results("bing", search_query)
                
                # 格式化结果
                results = [SearchResult(
                    title=url.split('/')[-1] if '/' in url else url,  # 使用URL的最后一部分作为标题
                    url=url,
                    snippet="",
                    source="Bing"
                ) for url in raw_results]
            
            # 缓存结果
            if results:
                try:
                    result_dicts = [r.to_dict() for r in results]
                    self.cache.set(search_query, "bing", result_dicts)
                except Exception as e:
                    self.logger.error(f"缓存Bing搜索结果出错: {e}")
                    
            return results[:num_results]
            
        except Exception as e:
            self.logger.error(f"Bing搜索出错: {e}")
            return []
    
    async def _async_pubmed_search(self, query: str, num_results: int = 10) -> List[Dict]:
        """执行PubMed搜索"""
        try:
            self.logger.info(f"执行PubMed搜索: {query}")
            # 检查缓存
            cached_results = self.cache.get(query, "pubmed")
            if cached_results is not None:
                return [{'url': url, 'title': url, 'snippet': ''} for url in cached_results][:num_results]
                
            # 如果没有缓存，执行搜索
            results = await fetch_search_results("pubmed", query)
            
            # 格式化结果
            formatted_results = [{'url': url, 'title': url, 'snippet': ''} for url in results][:num_results]
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"PubMed搜索出错: {e}")
            return []
    
    async def _async_scholar_search(self, query: str, num_results: int = 10) -> List[Dict]:
        """执行Google Scholar搜索"""
        try:
            self.logger.info(f"执行Google Scholar搜索: {query}")
            # 检查缓存
            cached_results = self.cache.get(query, "scholar")
            if cached_results is not None:
                return [{'url': url, 'title': url, 'snippet': ''} for url in cached_results][:num_results]
                
            # 如果没有缓存，执行搜索
            results = await fetch_search_results("scholar", query)
            
            # 格式化结果
            formatted_results = [{'url': url, 'title': url, 'snippet': ''} for url in results][:num_results]
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Google Scholar搜索出错: {e}")
            return []
    
    async def search(self, query: str, engines: Optional[List[str]] = None, num_results: int = 10) -> List[SearchResult]:
        """
        执行多引擎统一搜索
        
        Args:
            query: 搜索查询词
            engines: 要使用的搜索引擎列表，如果为空则使用默认引擎
            num_results: 最大返回结果数量
            
        Returns:
            搜索结果列表，包含标准化的SearchResult对象
        """
        # 如果没有指定引擎，使用默认引擎
        if engines is None:
            engines = ["google", "bing", "arxiv"]
        
        self.logger.info(f"启动多引擎搜索: '{query}', 引擎: {engines}")
        
        # 计算每个引擎的结果数
        results_per_engine = max(2, num_results // len(engines))
        all_results = []
        tasks = []
        
        # 并行启动所有搜索
        if "duckduckgo" in engines and hasattr(self, '_search_duckduckgo'):
            tasks.append(self._search_duckduckgo(query))
        
        if "google" in engines:
            tasks.append(self._async_google_search(query, results_per_engine))
        
        if "arxiv" in engines:
            tasks.append(self._search_arxiv(query, max(1, results_per_engine // 2)))
            
        # 选择带有兼容性的备用引擎
        if "bing" in engines:
            tasks.append(self._async_bing_search(query, results_per_engine))
            
        if "pubmed" in engines:
            tasks.append(self._async_pubmed_search(query, results_per_engine))
            
        if "scholar" in engines:
            tasks.append(self._async_scholar_search(query, results_per_engine))
        
        # 等待所有搜索完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        engine_result_counts = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"搜索错误: {result}")
            elif isinstance(result, list):
                # 确保所有结果都是SearchResult对象
                for item in result:
                    try:
                        source = None
                        if isinstance(item, SearchResult):
                            all_results.append(item)
                            source = item.source
                        elif isinstance(item, dict) and 'title' in item and 'url' in item and 'snippet' in item and 'source' in item:
                            all_results.append(SearchResult(**item))
                            source = item['source']
                        # 处理googlesearch.SearchResult对象
                        elif hasattr(item, 'title') and hasattr(item, 'url'):
                            # 将googlesearch.SearchResult转换为我们的SearchResult
                            snippet = ""
                            if hasattr(item, 'description'):
                                snippet = item.description
                            
                            all_results.append(SearchResult(
                                title=item.title,
                                url=item.url,
                                snippet=snippet,
                                source="Google"
                            ))
                            source = "Google"
                        else:
                            self.logger.warning(f"跳过无效的搜索结果: {type(item)}")
                            continue
                            
                        # 增加引擎计数
                        if source:
                            engine_result_counts[source] = engine_result_counts.get(source, 0) + 1
                    except Exception as e:
                        self.logger.error(f"处理搜索结果出错: {e}")
        
        # 合并并限制结果
        processed_results = self._process_search_results(all_results, query, num_results)
        
        # 统计并输出每个搜索引擎的结果数量
        engine_stats = [f"{engine}: {count}个结果" for engine, count in engine_result_counts.items()]
        engine_stats_str = "\n  - ".join(["各搜索引擎返回结果统计:"] + engine_stats)
        self.logger.info(engine_stats_str)
        
        # 输出总结果数
        self.logger.info(f"统一搜索器共处理{len(all_results)}个原始结果，返回{len(processed_results)}个去重结果")
        return processed_results
    
    def _process_search_results(self, results: List[SearchResult], query: str, max_results: int) -> List[SearchResult]:
        """
        处理搜索结果：去重、排序和限制结果数量
        
        Args:
            results: 原始搜索结果列表
            query: 原始查询词
            max_results: 最大返回结果数量
        
        Returns:
            处理后的搜索结果列表
        """
        if not results:
            return []
            
        # 去重 - 按URL去重
        filtered_results = []
        seen_urls = set()
        
        for result in results:
            url = result.url.strip() if hasattr(result, 'url') and result.url else ""
            if not url or url in seen_urls:
                continue
                
            seen_urls.add(url)
            filtered_results.append(result)
        
        # 为结果打分 - 综合考虑来源、排名、查询匹配度等
        scored_results = []
        
        # 引擎权重
        engine_weights = {
            "Google": 1.0,
            "Bing": 0.8,
            "PubMed": 1.2 if "medical" in query.lower() else 0.9,
            "Scholar": 1.1 if "research" in query.lower() else 0.9,
            "DuckDuckGo": 0.85,
            "Backup": 0.6
        }
        
        for i, result in enumerate(filtered_results):
            score = 0.0
            
            # 基于来源引擎的基础分
            source = result.source if hasattr(result, 'source') and result.source else "unknown"
            weight = engine_weights.get(source, 0.7)
            score += weight
            
            # 结果位置因素 - 早期结果得分更高
            position_factor = 1.0 - min(0.5, (i * 0.02))  # 最多降低0.5分
            score *= position_factor
            
            # 检查标题和摘要中是否包含查询词 - 提升相关度
            query_terms = set(query.lower().split())
            if hasattr(result, 'title') and result.title:
                title_words = set(result.title.lower().split())
                matches = query_terms.intersection(title_words)
                if matches:
                    score += len(matches) * 0.2
            
            if hasattr(result, 'snippet') and result.snippet:
                snippet_words = set(result.snippet.lower().split())
                matches = query_terms.intersection(snippet_words)
                if matches:
                    score += len(matches) * 0.1
            
            # 域名可信度评估
            if hasattr(result, 'url') and result.url:
                try:
                    domain = urllib.parse.urlparse(result.url).netloc
                    # 教育和政府网站得分更高
                    if domain.endswith('.edu') or domain.endswith('.gov') or domain.endswith('.org'):
                        score += 0.5
                    # 医学相关域名得分更高
                    medical_domains = ['pubmed', 'ncbi.nlm.nih', 'nejm', 'thelancet', 'who.int', 'mayoclinic', 'nih.gov']
                    if any(med_domain in domain for med_domain in medical_domains):
                        score += 0.7
                except Exception:
                    pass
            
            scored_results.append((score, result))
        
        # 根据分数排序
        scored_results.sort(reverse=True, key=lambda x: x[0])
        
        # 返回前max_results个结果
        return [result for _, result in scored_results[:max_results]]

# 全局统一搜索器实例
unified_searcher = UnifiedSearcher()

async def generate_medical_urls(query: str, intent_data: Dict) -> List[Dict]:
    """通过调用统一搜索器生成医学领域的URL列表，返回完整的搜索结果对象"""
    # 使用标准搜索引擎组合
    engines_to_use = ["google", "bing", "arxiv"]
    
    logger.info(f"将使用搜索引擎: {', '.join(engines_to_use)}")
    
    # 不使用增强查询，直接传入用户原始查询
    logger.info(f"执行查询: {query}")
    
    # 使用统一搜索器执行查询
    search_results = await unified_searcher.search(query, engines=engines_to_use, num_results=15)
    
    # 转换SearchResult对象为统一格式的字典
    final_results = []
    seen_urls = set()  # 用于去重
    
    for result in search_results:
        # 转换SearchResult对象为字典
        if isinstance(result, SearchResult):
            if result.url and result.url not in seen_urls:
                seen_urls.add(result.url)
                # 转换为字典并确保包含target字段
                result_dict = result.to_dict()
                # 如果没有target字段，使用URL作为target
                if not result_dict.get('target'):
                    result_dict['target'] = result.url
                final_results.append(result_dict)
        # 处理已经是字典格式的结果
        elif isinstance(result, dict) and 'url' in result:
            if result['url'] and result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                # 确保有target字段
                if 'target' not in result:
                    result['target'] = result['url']
                final_results.append(result)
    
    logger.info(f"搜索器共返回{len(final_results)}个结果")
    
    # 如果没有找到结果，返回默认的医学网站
    if not final_results:
        default_urls = [
            "https://pubmed.ncbi.nlm.nih.gov/",
            "https://www.nejm.org/",
            "https://www.thelancet.com/",
            "https://jamanetwork.com/",
            "https://www.bmj.com/"
        ]
        return [{
            'url': url,
            'title': url.split('/')[-2] if url.endswith('/') else url.split('/')[-1],
            'snippet': '',
            'source': 'default',
            'target': url
        } for url in default_urls]
    
    return final_results


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
        },
        "search_info": {
            "used_engines": [],
            "search_query": "",
            "result_count": 0
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
    
    #------ 使用标准搜索功能生成新的URL列表 ------
    logger.info(f"开始进行搜索: {user_input}")
    
    # 调用标准搜索函数获取医学URL
    try:
        # 使用标准搜索方法获取URL及完整搜索结果
        generated_results = await generate_medical_urls(user_input, intent_data)
        
        # 存储搜索相关信息
        result["search_info"] = {
            "used_engines": ["google", "bing", "arxiv"],  # 使用标准搜索引擎组合
            "search_query": user_input,
            "result_count": len(generated_results)
        }
        
    except Exception as e:
        # 如果搜索失败，记录错误并使用默认URL
        logger.error(f"搜索失败: {e}")
        default_urls = [
            "https://pubmed.ncbi.nlm.nih.gov/",
            "https://www.nejm.org/",
            "https://www.thelancet.com/",
            "https://jamanetwork.com/",
            "https://www.bmj.com/"
        ]
        # 创建默认的搜索结果字典
        generated_results = [{
            'url': url,
            'title': url.split('/')[-2] if url.endswith('/') else url.split('/')[-1],
            'snippet': '',
            'source': 'default',
            'target': url
        } for url in default_urls]
        
        result["search_info"] = {
            "used_engines": ["google", "bing", "arxiv"],
            "search_query": user_input,
            "result_count": len(generated_results),
            "error": str(e)
        }
    
    # 对每个生成的搜索结果进行完整验证
    generated_targets = []
    valid_generated_count = 0
    
    for i, result_item in enumerate(generated_results):
        # 确保我们有URL
        url = result_item.get('url', '')
        if not url:
            logger.warning(f"搜索结果中缺少URL: {result_item}")
            continue
            
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
            
            # 创建目标数据，保留原始搜索结果的其他字段
            url_data = {
                "url": url,
                "keywords": intent_data.get('intent_analysis', {}).get('key_terms', []),
                "source": result_item.get('source', 'search_engine'),
                "relevance_score": relevance_score,
                "title": result_item.get('title', ''),
                "snippet": result_item.get('snippet', ''),
                "target": result_item.get('target', url)  # 确保target字段存在
            }
            
            # 如果有其他元数据，也添加进来
            if 'metadata' in result_item and isinstance(result_item['metadata'], dict):
                for k, v in result_item['metadata'].items():
                    if k not in url_data:  # 避免覆盖已有字段
                        url_data[k] = v
                        
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
    
    # 添加搜索时间戳
    result["search_info"]["timestamp"] = datetime.now().isoformat()

    # print(json.dumps(result, ensure_ascii=False, indent=4))
    
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
