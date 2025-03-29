"""
动态优先级分配引擎

根据技术文档规范实现URL优先级队列管理系统，支持:
- 领域价值评估：医疗类网址通过预置权威域名清单（如.gov/.edu后缀）获得基础加权
- 时效性评估：基于网页中检测到的发布时间信息（优先抓取近6个月更新的内容）
- 需求匹配度：通过语义向量计算输入关键词与网页历史摘要的相似度
"""

import queue
import threading
import time
import yaml
import os
import re
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urlparse
import heapq
import json

# 导入DeepSeek API封装
from libs.deepseek_client.api_wrapper import DeepseekClient

logger = logging.getLogger(__name__)

@dataclass
class CrawlTask:
    """爬取任务对象，包含URL、优先级及相关元数据"""
    url: str
    priority: float  # 优先级分数，0-100，值越高优先级越高
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_attempt: Optional[float] = None
    retry_count: int = 0
    protection_level: str = 'basic'  # 可选值: basic, medium, high
    
    # 用于优先级队列的比较方法
    def __lt__(self, other):
        return self.priority > other.priority  # 注意这里是反向比较，让高优先级先出队
    
    def to_dict(self) -> Dict[str, Any]:
        """将任务转换为字典格式用于序列化"""
        return {
            'url': self.url,
            'priority': self.priority,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'last_attempt': self.last_attempt,
            'retry_count': self.retry_count,
            'protection_level': self.protection_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlTask':
        """从字典恢复任务对象"""
        return cls(
            url=data['url'],
            priority=data['priority'],
            metadata=data['metadata'],
            created_at=data['created_at'],
            last_attempt=data['last_attempt'],
            retry_count=data['retry_count'],
            protection_level=data['protection_level']
        )


class PriorityQueue:
    """
    优先级队列实现，支持以下功能:
    - 基于优先级的任务调度
    - 持久化存储和恢复
    - 防止任务重复
    - 优先级动态调整
    """
    def __init__(self, config_path: str = None, deepseek_client: Optional[Any] = None):
        self.queue = []  # heapq based priority queue
        self._lock = threading.RLock()
        self.seen_urls = set()  # 防止URL重复
        self.config_path = config_path or os.path.join('config', 'priority_rules.yaml')
        self.config = self._load_config()
        
        # 初始化DeepSeek客户端
        self.deepseek_client = deepseek_client or DeepseekClient()
        
        # 一些统计数据
        self.total_enqueued = 0
        self.total_processed = 0
    
    def _load_config(self) -> Dict:
        """加载优先级规则配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            else:
                logger.warning(f"配置文件 {self.config_path} 不存在，使用默认配置")
                return {
                    'authority_domains': {
                        'gov': 30,
                        'edu': 25,
                        'org': 20,
                        'nejm.org': 40,
                        'pubmed': 35,
                        'nih.gov': 40,
                        'who.int': 40,
                        'cdc.gov': 35,
                        'mayoclinic.org': 30,
                        'medscape.com': 30
                    },
                    'recency_weights': {
                        'within_week': 25,
                        'within_month': 20,
                        'within_6months': 15,
                        'within_year': 10,
                        'older': 0
                    },
                    'content_weights': {
                        'clinical_trial': 45,
                        'research_paper': 40,
                        'treatment_guideline': 45,
                        'case_study': 35,
                        'news': 20
                    },
                    'retry_penalties': {
                        'max_retries': 3,
                        'penalty_per_retry': 5
                    }
                }
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}

    async def calculate_priority(self, url: str, metadata: Dict = None) -> Tuple[float, str]:
        """
        计算URL的优先级分数
        
        参数:
            url: 要评估的URL
            metadata: 包含URL相关信息的元数据，如标题、摘要等
            
        返回:
            优先级分数(0-100)和防护等级估计
        """
        metadata = metadata or {}
        base_score = 50  # 基础分数
        
        # 1. 领域价值评估
        domain_score = self._evaluate_domain_authority(url)
        
        # 2. 时效性评估
        recency_score = self._evaluate_recency(metadata.get('published_date'))
        
        # 3. 内容关联性评估
        content_score = await self._evaluate_content_relevance(url, metadata)
        
        # 综合评分，基于配置的权重
        weighted_score = domain_score + recency_score + content_score
        
        # 如果有重试，应用重试惩罚
        retry_count = metadata.get('retry_count', 0)
        retry_penalty = self.config.get('retry_penalties', {}).get('penalty_per_retry', 5) * retry_count
        
        final_score = max(0, min(100, weighted_score - retry_penalty))
        
        # 估计防护等级
        protection_level = self._estimate_protection_level(url, metadata)
        
        return final_score, protection_level
    
    def _evaluate_domain_authority(self, url: str) -> float:
        """评估URL的域名权威性，返回加权分数"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # 从配置中获取域名权重
            domain_weights = self.config.get('authority_domains', {})
            
            # 检查完整域名匹配
            for auth_domain, weight in domain_weights.items():
                if auth_domain in domain:
                    return float(weight)
            
            # 检查域名后缀
            for suffix, weight in domain_weights.items():
                if domain.endswith(f'.{suffix}'):
                    return float(weight)
            
            # 默认分数
            return 10.0
        except Exception as e:
            logger.error(f"域名评估错误: {e}")
            return 10.0
    
    def _evaluate_recency(self, date_str: Optional[str]) -> float:
        """评估内容的时效性"""
        if not date_str:
            return 0.0
            
        try:
            # 尝试解析各种日期格式
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%b %d, %Y', '%B %d, %Y']:
                try:
                    publish_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                # 如果没有匹配的格式，尝试从字符串中提取年月日
                date_match = re.search(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', date_str)
                if date_match:
                    year, month, day = map(int, date_match.groups())
                    publish_date = datetime(year, month, day)
                else:
                    return 0.0
            
            # 计算发布时间与当前时间的差异
            days_diff = (datetime.now() - publish_date).days
            
            # 根据配置分配时效性分数
            recency_weights = self.config.get('recency_weights', {})
            
            if days_diff <= 7:  # 一周内
                return float(recency_weights.get('within_week', 25))
            elif days_diff <= 30:  # 一个月内
                return float(recency_weights.get('within_month', 20))
            elif days_diff <= 180:  # 六个月内
                return float(recency_weights.get('within_6months', 15))
            elif days_diff <= 365:  # 一年内
                return float(recency_weights.get('within_year', 10))
            else:  # 更早
                return float(recency_weights.get('older', 0))
        except Exception as e:
            logger.error(f"时效性评估错误: {e}")
            return 0.0

    async def _evaluate_content_relevance(self, url: str, metadata: Dict) -> float:
        """
        评估内容相关性
        
        这里我们可以选择:
        1. 基于规则的简单匹配
        2. 使用DeepSeek API进行更智能的评估
        """
        # 基础匹配评分
        content_score = 0.0
        content_weights = self.config.get('content_weights', {})
        
        # 标题和摘要文本
        title = metadata.get('title', '')
        description = metadata.get('description', '')
        combined_text = f"{title} {description}".lower()
        
        # 基于关键词的匹配
        for content_type, weight in content_weights.items():
            keywords = {
                'clinical_trial': ['clinical trial', '临床试验', 'phase', '阶段研究', 'randomized', '随机对照'],
                'research_paper': ['research', '研究', 'study', 'journal', '期刊', 'paper', '论文'],
                'treatment_guideline': ['guideline', '指南', 'protocol', '方案', 'treatment', '治疗方法'],
                'case_study': ['case study', '病例研究', 'case report', '病例报告'],
                'news': ['news', '新闻', 'update', '更新', 'latest', '最新']
            }.get(content_type, [])
            
            if any(kw in combined_text for kw in keywords):
                content_score += float(weight)
        
        # 如果有足够信息，可以使用DeepSeek进行更精确的评估
        if (title or description) and self.deepseek_client:
            try:
                llm_score = await self.prioritize_with_llm(url, title, description)
                # 综合规则评分和LLM评分
                content_score = max(content_score, llm_score)  # 取较高的分数
            except Exception as e:
                logger.error(f"DeepSeek内容评估错误: {e}")
        
        return min(45.0, content_score)  # 上限45分

    async def prioritize_with_llm(self, url: str, title: str = '', description: str = '') -> float:
        """使用DeepSeek API评估医疗页面优先级"""
        snippet = f"标题: {title}\n摘要: {description}"
        
        prompt = f"""评估医疗页面优先级：
        URL：{url}
        内容：{snippet}
        
        请输出：
        {{
            "priority": 1-10, 
            "reason": "包含临床试验数据/权威指南/新型疗法等"
        }}"""
        
        try:
            result = await self.deepseek_client.async_chat(prompt)
            # 解析JSON响应
            if isinstance(result, str):
                try:
                    data = json.loads(result)
                    priority = float(data.get('priority', 5))
                    # 转换为0-45的分数范围
                    return priority * 4.5
                except:
                    # 如果无法解析JSON，尝试直接从文本中提取数字
                    match = re.search(r'"priority"\s*:\s*(\d+(?:\.\d+)?)', result)
                    if match:
                        priority = float(match.group(1))
                        return priority * 4.5
            return 25.0  # 默认中等优先级
        except Exception as e:
            logger.error(f"DeepSeek API调用错误: {e}")
            return 25.0

    def _estimate_protection_level(self, url: str, metadata: Dict) -> str:
        """估计URL的防护等级，用于选择适当的爬取策略"""
        domain = urlparse(url).netloc.lower()
        
        # 已知高防护网站列表
        high_protection_sites = [
            'nejm.org', 'sciencedirect.com', 'nature.com', 
            'onlinelibrary.wiley.com', 'academic.oup.com',
            'jamanetwork.com', 'bmj.com', 'thelancet.com'
        ]
        
        # 中等防护网站
        medium_protection_sites = [
            'pubmed.ncbi.nlm.nih.gov', 'medscape.com', 'mayoclinic.org',
            'medlineplus.gov', 'webmd.com', 'uptodate.com'
        ]
        
        # 检查高防护网站
        if any(site in domain for site in high_protection_sites):
            return 'high'
            
        # 检查中等防护网站
        if any(site in domain for site in medium_protection_sites):
            return 'medium'
            
        # 检查元数据中的历史记录
        if metadata.get('has_captcha') or metadata.get('previous_blocks'):
            return 'high'
            
        if metadata.get('requires_js') or metadata.get('previous_timeouts'):
            return 'medium'
        
        # 默认为基础防护
        return 'basic'

    async def enqueue(self, url: str, metadata: Dict = None) -> Optional[CrawlTask]:
        """
        将URL添加到优先级队列
        
        参数:
            url: 要爬取的URL
            metadata: URL相关元数据
            
        返回:
            成功入队的CrawlTask或None（如果URL已存在）
        """
        # URL标准化和去重
        url = url.strip()
        
        with self._lock:
            if url in self.seen_urls:
                return None
                
            self.seen_urls.add(url)
        
        # 计算优先级分数
        metadata = metadata or {}
        priority, protection_level = await self.calculate_priority(url, metadata)
        
        # 创建爬取任务
        task = CrawlTask(
            url=url,
            priority=priority,
            metadata=metadata,
            protection_level=protection_level
        )
        
        # 添加到优先级队列
        with self._lock:
            heapq.heappush(self.queue, task)
            self.total_enqueued += 1
        
        logger.debug(f"已将URL添加到队列: {url} (优先级: {priority:.2f}, 防护: {protection_level})")
        return task
    
    async def enqueue_batch(self, urls: List[str], metadata_list: List[Dict] = None) -> List[CrawlTask]:
        """批量将URL添加到优先级队列"""
        metadata_list = metadata_list or [{}] * len(urls)
        tasks = []
        
        for url, metadata in zip(urls, metadata_list):
            task = await self.enqueue(url, metadata)
            if task:
                tasks.append(task)
                
        return tasks
    
    def dequeue(self) -> Optional[CrawlTask]:
        """从队列中获取优先级最高的任务"""
        with self._lock:
            if not self.queue:
                return None
                
            task = heapq.heappop(self.queue)
            task.last_attempt = time.time()
            self.total_processed += 1
            
            return task
    
    def requeue(self, task: CrawlTask, priority_adjustment: float = -5.0):
        """将任务重新加入队列，通常用于重试失败的任务"""
        with self._lock:
            # 更新重试计数和优先级
            task.retry_count += 1
            task.priority = max(0, task.priority + priority_adjustment)
            task.last_attempt = time.time()
            
            # 检查是否超过最大重试次数
            max_retries = self.config.get('retry_penalties', {}).get('max_retries', 3)
            if task.retry_count <= max_retries:
                heapq.heappush(self.queue, task)
                logger.debug(f"任务重新入队: {task.url} (优先级: {task.priority:.2f}, 重试次数: {task.retry_count})")
            else:
                logger.warning(f"任务超过最大重试次数: {task.url}")
    
    def size(self) -> int:
        """获取当前队列大小"""
        with self._lock:
            return len(self.queue)
    
    def is_empty(self) -> bool:
        """检查队列是否为空"""
        with self._lock:
            return len(self.queue) == 0
    
    def clear(self):
        """清空队列"""
        with self._lock:
            self.queue = []
            self.seen_urls = set()
    
    def save_state(self, filepath: str):
        """保存队列状态到文件"""
        with self._lock:
            state = {
                'queue': [task.to_dict() for task in self.queue],
                'seen_urls': list(self.seen_urls),
                'stats': {
                    'total_enqueued': self.total_enqueued,
                    'total_processed': self.total_processed
                }
            }
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                logger.info(f"队列状态已保存到: {filepath}")
            except Exception as e:
                logger.error(f"保存队列状态失败: {e}")
    
    def load_state(self, filepath: str):
        """从文件加载队列状态"""
        try:
            if not os.path.exists(filepath):
                logger.warning(f"队列状态文件不存在: {filepath}")
                return False
                
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            with self._lock:
                # 恢复队列
                self.queue = []
                for task_dict in state.get('queue', []):
                    heapq.heappush(self.queue, CrawlTask.from_dict(task_dict))
                
                # 恢复已见URL集合
                self.seen_urls = set(state.get('seen_urls', []))
                
                # 恢复统计数据
                stats = state.get('stats', {})
                self.total_enqueued = stats.get('total_enqueued', 0)
                self.total_processed = stats.get('total_processed', 0)
                
                logger.info(f"队列状态已从 {filepath} 加载，当前队列大小: {len(self.queue)}")
                return True
        except Exception as e:
            logger.error(f"加载队列状态失败: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """获取队列统计信息"""
        with self._lock:
            priority_stats = {}
            protection_stats = {'high': 0, 'medium': 0, 'basic': 0}
            
            # 计算优先级区间分布
            for task in self.queue:
                # 优先级统计 (分10个区间)
                interval = int(task.priority // 10) * 10
                priority_stats[interval] = priority_stats.get(interval, 0) + 1
                
                # 防护等级统计
                protection_stats[task.protection_level] = protection_stats.get(task.protection_level, 0) + 1
            
            return {
                'queue_size': len(self.queue),
                'seen_urls': len(self.seen_urls),
                'total_enqueued': self.total_enqueued,
                'total_processed': self.total_processed,
                'priority_distribution': priority_stats,
                'protection_levels': protection_stats
            }