#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
URL验证模块 - 输入处理微服务的一部分
负责URL的语法验证、网络可达性检测和内容相关性预判
"""

import re
import random
import asyncio
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse
import ftfy
import aiohttp
from aiohttp import ClientError
import logging
import yaml
import os
from pathlib import Path

# 开发模式设置 - 在开发/测试环境中跳过某些耗时的检查
DEV_MODE = True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 默认用户代理列表，用于网络请求伪装
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
]

# 加载配置文件
def load_config():
    """加载URL验证规则配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'url_rules.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"无法加载配置文件: {e}")
        # 返回默认配置
        return {
            'timeout': 5,
            'retry_policy': {
                'max_attempts': 3,
                'backoff': [1, 3, 5]
            },
            'blacklist': ['*.gov']
        }

CONFIG = load_config()

def detect_url(text: str) -> List[str]:
    """
    从文本中检测并提取URL
    
    Args:
        text: 输入文本
    
    Returns:
        检测到的URL列表
    """
    # 首先修复可能的乱码
    text = ftfy.fix_text(text)
    
    # 使用改进版RFC3986正则表达式
    pattern = r"https?://(?:[-\w]+\.)+[a-z]{2,}(?:/[^/\s]*)*"
    return re.findall(pattern, text, flags=re.IGNORECASE)

def validate_syntax(url: str) -> bool:
    """
    验证URL语法是否有效
    
    Args:
        url: 待验证的URL
    
    Returns:
        如果URL语法有效则返回True，否则返回False
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception as e:
        logger.error(f"URL语法验证失败: {url}, 原因: {e}")
        return False

def is_blacklisted(url: str) -> bool:
    """
    检查URL是否在黑名单中
    
    Args:
        url: 待检查的URL
    
    Returns:
        如果URL在黑名单中则返回True，否则返回False
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
    for pattern in CONFIG.get('blacklist', []):
        if pattern.startswith('*.'):
            suffix = pattern[2:]
            if domain.endswith(suffix):
                return True
        elif pattern == domain:
            return True
    
    return False

async def check_liveness(url: str) -> bool:
    """
    异步检查URL的网络可达性
    
    Args:
        url: 待检查的URL
    
    Returns:
        如果URL可达则返回True，否则返回False
    """
    # 获取配置的超时和重试策略
    timeout = CONFIG.get('timeout', 5)
    retry_policy = CONFIG.get('retry_policy', {'max_attempts': 3, 'backoff': [1, 3, 5]})
    max_attempts = retry_policy.get('max_attempts', 3)
    backoff_times = retry_policy.get('backoff', [1, 3, 5])
    
    # 日志记录检查开始
    logger.info(f"[可达性检查] 开始检查URL(最多{max_attempts}次尝试, 超时{timeout}秒): {url}")
    start_time = asyncio.get_event_loop().time()
    
    for attempt in range(max_attempts):
        attempt_start = asyncio.get_event_loop().time()
        logger.info(f"[可达性检查] 尝试 {attempt+1}/{max_attempts} 开始: {url}")
        
        try:
            # 设置随机用户代理进行伪装
            user_agent = random.choice(USER_AGENTS)
            headers = {'User-Agent': user_agent}
            
            async with aiohttp.ClientSession() as session:
                logger.debug(f"[可达性检查] 发送HEAD请求到: {url}")
                
                async with session.head(
                    url, 
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True
                ) as resp:
                    attempt_duration = asyncio.get_event_loop().time() - attempt_start
                    is_reachable = 200 <= resp.status < 400  # 认为2xx和3xx状态码是可达的
                    
                    if is_reachable:
                        logger.info(f"[可达性检查] 成功! URL: {url}, 状态码: {resp.status}, 耗时: {attempt_duration:.2f}秒")
                    else:
                        logger.warning(f"[可达性检查] 失败! URL: {url}, 状态码: {resp.status}, 耗时: {attempt_duration:.2f}秒")
                    
                    total_duration = asyncio.get_event_loop().time() - start_time
                    logger.info(f"[可达性检查] 完成检查! URL: {url}, 结果: {'可达' if is_reachable else '不可达'}, 总耗时: {total_duration:.2f}秒")
                    return is_reachable
                    
        except aiohttp.ClientConnectorError as e:
            attempt_duration = asyncio.get_event_loop().time() - attempt_start
            logger.warning(f"[可达性检查] 连接错误! 尝试 {attempt+1}/{max_attempts}, URL: {url}, 原因: {str(e)}, 耗时: {attempt_duration:.2f}秒")
        except aiohttp.ClientResponseError as e:
            attempt_duration = asyncio.get_event_loop().time() - attempt_start
            logger.warning(f"[可达性检查] 响应错误! 尝试 {attempt+1}/{max_attempts}, URL: {url}, 状态码: {e.status}, 原因: {str(e)}, 耗时: {attempt_duration:.2f}秒")
        except asyncio.TimeoutError:
            attempt_duration = asyncio.get_event_loop().time() - attempt_start
            logger.warning(f"[可达性检查] 超时! 尝试 {attempt+1}/{max_attempts}, URL: {url}, 超过{timeout}秒无响应, 耗时: {attempt_duration:.2f}秒")
        except Exception as e:
            attempt_duration = asyncio.get_event_loop().time() - attempt_start
            logger.warning(f"[可达性检查] 未知错误! 尝试 {attempt+1}/{max_attempts}, URL: {url}, 错误类型: {type(e).__name__}, 原因: {str(e)}, 耗时: {attempt_duration:.2f}秒")
            
        if attempt < max_attempts - 1:
            # 在下一次重试前等待
            backoff_time = backoff_times[min(attempt, len(backoff_times) - 1)]
            logger.info(f"[可达性检查] 将在{backoff_time}秒后重试, URL: {url}")
            await asyncio.sleep(backoff_time)
        else:
            total_duration = asyncio.get_event_loop().time() - start_time
            logger.error(f"[可达性检查] 所有尝试均失败! URL: {url}, 总耗时: {total_duration:.2f}秒")
            return False
    
    # 这行代码应该永远不会执行，但为了安全起见保留
    return False

def predict_relevance(url: str, user_query: str) -> float:
    """
    预测URL与用户查询的相关性
    
    Args:
        url: 待评估的URL
        user_query: 用户查询文本
    
    Returns:
        相关性得分，范围0-1
    """
    # 这里应该使用语义向量模型计算相似度
    # 由于我们还没有集成DeepSeek, 先使用简单的关键词匹配做一个临时实现
    
    # 简化版相关性计算：基于域名与查询的关键词匹配
    domain = urlparse(url).netloc
    path = urlparse(url).path
    
    # 将域名和路径分解为关键词
    url_words = set(re.findall(r'\w+', domain.lower() + " " + path.lower()))
    query_words = set(re.findall(r'\w+', user_query.lower()))
    
    # 计算交集大小
    intersection = url_words.intersection(query_words)
    
    # 如果没有交集，返回一个较低的基础分
    if not intersection:
        return 0.3
    
    # 计算Jaccard相似度
    similarity = len(intersection) / len(url_words.union(query_words))
    
    # 加权计算 (确保分数在0-1之间)
    return min(max(0.3 + similarity * 0.7, 0), 1)

async def validate_url(url: str, user_query: str = None) -> Dict:
    """
    URL的完整验证流程
    
    Args:
        url: 待验证的URL
        user_query: 用户查询文本，用于相关性计算
    
    Returns:
        验证结果字典，包含验证状态和详细信息
    """
    result = {
        "url": url,
        "valid": False,
        "reason": None,
        "relevance_score": None
    }
    
    # 步骤1: 语法验证
    if not validate_syntax(url):
        result["reason"] = "URL语法无效"
        return result
    
    # 步骤2: 黑名单检查
    if is_blacklisted(url):
        result["reason"] = "URL在黑名单中"
        return result
    
    # 步骤3: 网络可达性验证
    # 在开发模式下，跳过网络可达性检查
    is_reachable = True
    
    if not DEV_MODE:
        # 如果不是开发模式，才进行真正的网络可达性检查
        logger.info(f"[URL验证] 执行网络可达性检查: {url}")
        is_reachable = await check_liveness(url)
        logger.info(f"[URL验证] 网络可达性检查结果: {url} - {'可达' if is_reachable else '不可达'}")
        if not is_reachable:
            result["reason"] = "URL不可达"
            logger.warning(f"[URL验证] URL验证失败 - 网络不可达: {url}")
            return result
    else:
        logger.info(f"[URL验证] 开发模式：跳过URL可达性检查: {url} (假设为可达)")
    
    # 步骤4: 相关性预判 (如果提供了用户查询)
    if user_query:
        relevance_score = predict_relevance(url, user_query)
        result["relevance_score"] = relevance_score
        
        # 在开发模式下，降低相关性阈值
        relevance_threshold = 0.1 if DEV_MODE else 0.5
        
        # 只有相关性得分超过阈值才视为有效
        if relevance_score >= relevance_threshold:
            result["valid"] = True
        else:
            result["reason"] = "相关性过低"
            result["valid"] = False
    else:
        # 如果没有提供用户查询，则只要网络可达就认为是有效的
        result["valid"] = True
    
    return result

async def batch_validate_urls(urls: List[str], user_query: str = None) -> List[Dict]:
    """
    批量验证多个URL
    
    Args:
        urls: URL列表
        user_query: 用户查询文本
    
    Returns:
        每个URL的验证结果列表
    """
    tasks = [validate_url(url, user_query) for url in urls]
    return await asyncio.gather(*tasks)

# 入口函数，用于从外部调用
async def process_input(text: str) -> Dict:
    """
    处理用户输入，检测并验证其中的URL
    
    Args:
        text: 用户输入文本
    
    Returns:
        处理结果，包含检测到的URL及其验证状态
    """
    # 检测文本中的URL
    detected_urls = detect_url(text)
    
    result = {
        "input_text": text,
        "contains_urls": len(detected_urls) > 0,
        "detected_urls": detected_urls,
        "validated_urls": []
    }
    
    # 如果检测到URL，执行验证
    if detected_urls:
        validation_results = await batch_validate_urls(detected_urls, text)
        result["validated_urls"] = validation_results
        
        # 筛选有效的URL
        valid_urls = [r["url"] for r in validation_results if r["valid"]]
        result["valid_urls"] = valid_urls
        result["has_valid_urls"] = len(valid_urls) > 0
    else:
        result["valid_urls"] = []
        result["has_valid_urls"] = False
    
    return result

# 如果作为独立脚本运行，执行测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_text = sys.argv[1]
    else:
        # 默认测试文本
        test_text = "请爬取这个医疗期刊内容：https://www.nejm.org/coronary-disease 和 https://www.example.com/nonexistent"
    
    # 执行异步函数
    result = asyncio.run(process_input(test_text))
    
    # 打印结果
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))