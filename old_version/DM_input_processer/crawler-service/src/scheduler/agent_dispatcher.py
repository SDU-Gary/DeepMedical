"""
Agent分发器

根据技术文档规范实现爬虫Agent分发系统，负责：
- 根据任务优先级和防护等级选择合适的爬虫Agent
- 监控爬虫执行状态和结果
- 处理任务重试逻辑
- 更新流量和优先级数据
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any, Union, Tuple
import os
import json
from datetime import datetime
from urllib.parse import urlparse
import uuid

# 导入相关组件
from .priority_queue import PriorityQueue, CrawlTask

# 导入Agent实现
from ..agents.playwright_agent.agent import PlaywrightAgent
from ..agents.scrapy_agent.agent import ScrapyAgent

# 导入反爬组件
from ..anti_crawler.proxy_rotator import ProxyRotator
from ..anti_crawler.behavior_simulator import BehaviorSimulator

logger = logging.getLogger(__name__)

class AgentDispatcher:
    """
    Agent分发器，负责：
    1. 从优先级队列获取任务
    2. 根据任务特性选择合适的爬虫Agent
    3. 监控爬虫执行状态
    4. 处理结果和异常
    """
    def __init__(
        self,
        priority_queue: Optional[PriorityQueue] = None,
        playwright_agent: Optional[PlaywrightAgent] = None,
        scrapy_agent: Optional[ScrapyAgent] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        max_concurrent_tasks: int = 10,
        result_handler: Optional[Any] = None
    ):
        # 初始化组件
        self.priority_queue = priority_queue or PriorityQueue()
        self.playwright_agent = playwright_agent or PlaywrightAgent()
        self.scrapy_agent = scrapy_agent or ScrapyAgent()
        self.proxy_rotator = proxy_rotator or ProxyRotator()
        self.behavior_simulator = BehaviorSimulator()
        
        # 并发控制
        self.max_concurrent_tasks = max_concurrent_tasks
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # 结果处理器
        self.result_handler = result_handler
        
        # 任务记录和统计
        self.active_tasks = {}  # task_id -> task_info
        self.task_history = {}  # url -> [task_results]
        self.domain_stats = {}  # domain -> stats
        
        # 运行状态
        self.running = False
        self._main_task = None
        
    async def start(self):
        """启动分发器，开始处理队列中的任务"""
        if self.running:
            logger.warning("调度器已经在运行中")
            return
            
        logger.info("启动Agent调度器")
        self.running = True
        
        # 初始化Agent
        await self.playwright_agent.initialize()
        await self.scrapy_agent.initialize()
        
        # 启动主循环
        self._main_task = asyncio.create_task(self._dispatch_loop())
        
    async def stop(self):
        """停止分发器"""
        if not self.running:
            return
            
        logger.info("正在停止Agent调度器")
        self.running = False
        
        # 等待主循环结束
        if self._main_task:
            try:
                await asyncio.wait_for(self._main_task, timeout=5)
            except asyncio.TimeoutError:
                logger.warning("调度器主循环停止超时")
        
        # 等待所有活动任务完成
        if self.active_tasks:
            logger.info(f"等待 {len(self.active_tasks)} 个活动任务完成")
            try:
                pending_tasks = [task_info['task'] for task_info in self.active_tasks.values() 
                               if isinstance(task_info.get('task'), asyncio.Task)]
                if pending_tasks:
                    await asyncio.wait(pending_tasks, timeout=10)
            except Exception as e:
                logger.error(f"等待任务完成时出错: {e}")
        
        # 关闭Agent
        await self.playwright_agent.shutdown()
        await self.scrapy_agent.shutdown()
        
        logger.info("Agent调度器已停止")
    
    async def _dispatch_loop(self):
        """
        主调度循环，从队列中获取任务并分发给合适的Agent
        """
        try:
            while self.running:
                # 检查当前活跃任务数量
                active_count = len(self.active_tasks)
                if active_count >= self.max_concurrent_tasks:
                    # 已达到最大并发数，等待一些任务完成
                    await asyncio.sleep(0.5)
                    continue
                
                # 获取下一个任务
                crawl_task = self.priority_queue.dequeue()
                if not crawl_task:
                    # 队列为空，等待一段时间后重试
                    await asyncio.sleep(0.5)
                    continue
                
                # 处理任务
                task_id = str(uuid.uuid4())
                asyncio.create_task(self._process_task(task_id, crawl_task))
                
        except Exception as e:
            logger.error(f"调度循环出错: {e}")
            if self.running:  # 如果不是正常停止
                self.running = False
        
        logger.info("调度循环已结束")
    
    async def _process_task(self, task_id: str, crawl_task: CrawlTask):
        """
        处理单个爬取任务，选择合适的Agent并执行
        
        参数:
            task_id: 唯一任务标识符
            crawl_task: 要处理的爬取任务
        """
        url = crawl_task.url
        domain = urlparse(url).netloc
        
        # 更新任务状态
        self.active_tasks[task_id] = {
            'url': url,
            'start_time': time.time(),
            'status': 'initializing',
            'crawl_task': crawl_task
        }
        
        try:
            # 根据防护等级选择合适的Agent
            agent, strategy = self._select_agent_and_strategy(crawl_task)
            
            # 获取代理
            proxy = await self.proxy_rotator.get_proxy(domain, crawl_task.protection_level)
            
            # 更新任务状态
            self.active_tasks[task_id].update({
                'agent': agent.__class__.__name__,
                'protection_level': crawl_task.protection_level,
                'proxy': proxy,
                'status': 'running'
            })
            
            # 执行爬取任务
            logger.info(f"开始执行任务 {task_id}: {url} (优先级: {crawl_task.priority:.2f}, 防护等级: {crawl_task.protection_level})")
            
            # 设置任务执行环境
            execution_config = {
                'proxy': proxy,
                'headers': self._generate_headers(domain, crawl_task.protection_level),
                'timeout': self._calculate_timeout(crawl_task),
                'behavior': await self.behavior_simulator.generate_behavior(url, crawl_task.protection_level),
                'cookies': crawl_task.metadata.get('cookies'),
                'referrer': crawl_task.metadata.get('referrer')
            }
            
            # 执行爬取
            task = asyncio.create_task(agent.fetch(url, strategy, execution_config))
            self.active_tasks[task_id]['task'] = task
            result = await task
            
            # 处理结果
            await self._handle_result(task_id, crawl_task, result)
            
        except Exception as e:
            logger.error(f"处理任务 {task_id} 出错: {e}")
            # 处理异常
            await self._handle_error(task_id, crawl_task, str(e))
        finally:
            # 清理任务状态
            if task_id in self.active_tasks:
                self.active_tasks[task_id]['status'] = 'completed'
                self.active_tasks[task_id]['end_time'] = time.time()
                
                # 可选：删除活动任务记录或将其移至历史记录
                task_record = self.active_tasks.pop(task_id)
                
                # 更新域名统计
                self._update_domain_stats(domain, task_record)
    
    def _select_agent_and_strategy(self, crawl_task: CrawlTask) -> Tuple[Any, Dict]:
        """
        根据任务特性选择合适的Agent和策略
        
        参数:
            crawl_task: 爬取任务
            
        返回:
            元组(agent, strategy)
        """
        protection_level = crawl_task.protection_level
        url = crawl_task.url
        domain = urlparse(url).netloc
        
        # 检查高价值目标 (总分≥75% 或 含敏感医疗术语)
        high_value_target = crawl_task.priority >= 75 or self._contains_medical_terms(crawl_task)
        
        # 高防护或高价值目标使用Playwright
        if protection_level == 'high' or high_value_target:
            logger.debug(f"选择Playwright高级采集器处理: {url}")
            strategy = {
                'render_js': True,
                'wait_for_full_load': True,
                'emulate_user_interaction': True,
                'extract_metadata': True,
                'capture_screenshot': crawl_task.metadata.get('capture_screenshot', False)
            }
            return self.playwright_agent, strategy
        else:
            logger.debug(f"选择Scrapy基础采集器处理: {url}")
            strategy = {
                'render_js': False,
                'extract_links': True,
                'extract_metadata': True
            }
            return self.scrapy_agent, strategy
            
    def _contains_medical_terms(self, crawl_task: CrawlTask) -> bool:
        """检查任务是否包含医疗敏感术语"""
        # 医疗敏感术语列表
        medical_terms = [
            'clinical trial', '临床试验', 'randomized', '随机对照',
            'patient data', '患者数据', 'medical record', '医疗记录',
            'treatment protocol', '治疗方案', 'case study', '病例研究',
            'symptom', '症状', 'diagnosis', '诊断', 'prognosis', '预后'
        ]
        
        metadata = crawl_task.metadata
        title = metadata.get('title', '')
        description = metadata.get('description', '')
        url = crawl_task.url
        
        # 检查标题、描述和URL中是否包含医疗术语
        text_to_check = f"{title} {description} {url}".lower()
        return any(term.lower() in text_to_check for term in medical_terms)
    
    def _generate_headers(self, domain: str, protection_level: str) -> Dict:
        """生成适合当前目标的请求头"""
        # 基础请求头
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        # 根据防护等级增强请求头
        if protection_level == 'high':
            # 添加更多真实浏览器特性
            headers.update({
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1'
            })
            
            # 医学网站特殊请求头
            if any(x in domain for x in ['nejm.org', 'pubmed', 'nih.gov', 'mayoclinic']):
                headers.update({
                    'Referer': f'https://www.google.com/search?q=medical+research+{domain}',
                    'X-Requested-With': 'XMLHttpRequest'
                })
        
        return headers
    
    def _calculate_timeout(self, crawl_task: CrawlTask) -> int:
        """计算适合任务的超时时间"""
        # 基础超时时间
        base_timeout = 20
        
        # 根据防护等级调整
        if crawl_task.protection_level == 'high':
            base_timeout = 30
        elif crawl_task.protection_level == 'medium':
            base_timeout = 25
            
        # 根据重试次数加长超时
        retry_factor = 1 + (0.2 * crawl_task.retry_count)
        
        return int(base_timeout * retry_factor)
    
    async def _handle_result(self, task_id: str, crawl_task: CrawlTask, result: Dict):
        """
        处理爬取结果
        
        参数:
            task_id: 任务ID
            crawl_task: 原始爬取任务
            result: 爬取结果
        """
        url = crawl_task.url
        success = result.get('success', False)
        domain = urlparse(url).netloc
        
        if success:
            # 爬取成功
            logger.info(f"任务 {task_id} 成功: {url}")
            
            # 记录任务历史
            if url not in self.task_history:
                self.task_history[url] = []
            self.task_history[url].append({
                'timestamp': datetime.now().isoformat(),
                'success': True,
                'data_size': len(result.get('content', '')),
                'links_found': len(result.get('extracted_links', [])),
                'agent': self.active_tasks[task_id].get('agent')
            })
            
            # 处理提取的链接（可选）
            if 'extracted_links' in result and result['extracted_links']:
                await self._process_extracted_links(crawl_task, result['extracted_links'])
            
            # 如果有结果处理器，发送结果进行后续处理
            if self.result_handler:
                await self.result_handler.process_result(crawl_task, result)
                
            # 更新域名统计
            if domain not in self.domain_stats:
                self.domain_stats[domain] = {
                    'success_count': 0,
                    'fail_count': 0,
                    'total_size': 0,
                    'last_success': None
                }
            self.domain_stats[domain]['success_count'] += 1
            self.domain_stats[domain]['total_size'] += len(result.get('content', ''))
            self.domain_stats[domain]['last_success'] = datetime.now().isoformat()
            
        else:
            # 爬取失败，但不是错误
            logger.warning(f"任务 {task_id} 未返回有效内容: {url}")
            # 可以选择重试或记录为软失败
            error_code = result.get('error_code')
            if error_code in ['no_content', 'timeout', 'parsing_error']:
                await self._retry_task_if_needed(crawl_task, error_code)
            else:
                # 不明确的情况，默认处理为软失败
                await self._retry_task_if_needed(crawl_task, 'unknown')
    
    async def _handle_error(self, task_id: str, crawl_task: CrawlTask, error_message: str):
        """
        处理爬取过程中的错误
        
        参数:
            task_id: 任务ID
            crawl_task: 原始爬取任务
            error_message: 错误消息
        """
        url = crawl_task.url
        domain = urlparse(url).netloc
        
        logger.error(f"任务 {task_id} 错误: {url}, 错误: {error_message}")
        
        # 错误分类
        error_type = self._classify_error(error_message)
        
        # 记录任务历史
        if url not in self.task_history:
            self.task_history[url] = []
        self.task_history[url].append({
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'error_type': error_type,
            'error_message': error_message,
            'agent': self.active_tasks[task_id].get('agent')
        })
        
        # 更新域名统计
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {
                'success_count': 0,
                'fail_count': 0,
                'total_size': 0,
                'last_success': None
            }
        self.domain_stats[domain]['fail_count'] += 1
        
        # 根据错误类型决定是否重试
        await self._retry_task_if_needed(crawl_task, error_type)
    
    def _classify_error(self, error_message: str) -> str:
        """
        对错误消息进行分类
        
        参数:
            error_message: 错误消息
            
        返回:
            错误类型
        """
        error_message = error_message.lower()
        
        # 网络连接错误
        if any(x in error_message for x in ['connection', 'timeout', 'socket', 'reset', 'eof']):
            return 'network_error'
        
        # HTTP错误
        elif any(x in error_message for x in ['403', 'forbidden', '401', 'unauthorized']):
            return 'access_denied'
        elif any(x in error_message for x in ['404', 'not found']):
            return 'not_found'
        elif any(x in error_message for x in ['500', 'server error', '502', 'bad gateway']):
            return 'server_error'
        elif any(x in error_message for x in ['captcha', 'robot', 'verification']):
            return 'captcha_detected'
        
        # 解析错误
        elif any(x in error_message for x in ['parse', 'xpath', 'selector', 'element']):
            return 'parsing_error'
        
        # 其他错误
        else:
            return 'unknown_error'
    
    async def _retry_task_if_needed(self, crawl_task: CrawlTask, error_type: str):
        """
        根据条件决定是否重试任务
        
        参数:
            crawl_task: 爬取任务
            error_type: 错误类型
        """
        # 超出最大重试次数
        max_retries = {
            'network_error': 3,
            'access_denied': 2,
            'not_found': 1,  # 404通常不需要多次重试
            'server_error': 3,
            'captcha_detected': 2,
            'parsing_error': 2,
            'unknown_error': 2,
            'no_content': 1,
            'timeout': 3,
            'unknown': 1
        }.get(error_type, 2)
        
        if crawl_task.retry_count >= max_retries:
            logger.info(f"任务已达到最大重试次数({max_retries})，不再重试: {crawl_task.url}")
            return
        
        # 重试间隔（随机化以避免被检测）
        retry_delay = self._calculate_retry_delay(crawl_task.retry_count, error_type)
        
        # 创建新的任务副本进行重试
        new_task = crawl_task.clone()
        new_task.retry_count += 1
        
        # 根据错误类型调整任务属性
        if error_type == 'access_denied' or error_type == 'captcha_detected':
            # 提高防护等级
            new_task.protection_level = 'high'
            
            # 添加延迟
            new_task.metadata['min_delay'] = 5 + (new_task.retry_count * 2)
            
            # 考虑使用新代理
            new_task.metadata['force_new_proxy'] = True
        
        elif error_type == 'network_error' or error_type == 'server_error':
            # 网络或服务器问题，延长超时
            new_task.metadata['timeout_factor'] = 1.5
            
        # 放回队列，但优先级降低
        priority_decay = 0.85  # 每次重试优先级降低到原来的85%
        new_priority = new_task.priority * (priority_decay ** new_task.retry_count)
        
        logger.info(f"计划在 {retry_delay:.1f} 秒后重试任务 (尝试 #{new_task.retry_count+1}): {new_task.url}")
        
        # 延迟后将任务放回队列
        await asyncio.sleep(retry_delay)
        self.priority_queue.enqueue(new_task, new_priority)
    
    def _calculate_retry_delay(self, retry_count: int, error_type: str) -> float:
        """
        计算重试延迟时间
        
        参数:
            retry_count: 已重试次数
            error_type: 错误类型
            
        返回:
            延迟秒数
        """
        # 基础延迟
        base_delay = 5
        
        # 错误类型系数
        error_factors = {
            'network_error': 1.0,
            'access_denied': 2.5,
            'not_found': 0.5,
            'server_error': 1.5,
            'captcha_detected': 3.0,
            'parsing_error': 1.0,
            'unknown_error': 1.5,
            'no_content': 0.8,
            'timeout': 1.2,
            'unknown': 1.0
        }
        
        # 重试次数指数退避
        retry_factor = (2 ** retry_count)
        
        # 添加一些随机性
        jitter = random.uniform(0.8, 1.2)
        
        delay = base_delay * error_factors.get(error_type, 1.0) * retry_factor * jitter
        
        # 确保延迟在合理范围内
        return min(max(delay, 1.0), 300.0)  # 最小1秒，最大5分钟
    
    async def _process_extracted_links(self, source_task: CrawlTask, links: List[Dict]):
        """
        处理从页面提取的链接
        
        参数:
            source_task: 源任务
            links: 提取的链接列表，格式为 [{'url': '...', 'text': '...', 'context': '...'}]
        """
        if not links:
            return
            
        # 源URL信息
        source_url = source_task.url
        source_domain = urlparse(source_url).netloc
        
        # 链接计数
        added_count = 0
        
        for link_data in links:
            url = link_data.get('url')
            if not url or not url.startswith(('http://', 'https://')):
                continue
                
            # 分析链接
            link_domain = urlparse(url).netloc
            link_text = link_data.get('text', '')
            link_context = link_data.get('context', '')
            
            # 创建链接任务元数据
            metadata = {
                'source_url': source_url,
                'link_text': link_text,
                'link_context': link_context,
                'found_time': datetime.now().isoformat()
            }
            
            # 确定优先级因子
            priority_factors = {
                'same_domain': 1.2 if link_domain == source_domain else 0.8,  # 同域名链接优先级提高
                'medical_terms': 1.5 if self._text_contains_medical_terms(f"{link_text} {link_context}") else 1.0,
                'depth': 0.9 ** (source_task.metadata.get('depth', 0) + 1)  # 深度越深优先级越低
            }
            
            # 计算新链接的优先级（基于源任务，但有衰减）
            base_priority = source_task.priority * 0.7  # 基础衰减
            new_priority = base_priority * priority_factors['same_domain'] * \
                         priority_factors['medical_terms'] * priority_factors['depth']
            
            # 确定防护等级
            # 医学权威网站通常有更高的防护等级
            protection_level = 'high' if any(domain in link_domain for domain in 
                                         ['nejm.org', 'thelancet.com', 'jamanetwork.com', 'bmj.com', 
                                          'pubmed', 'nih.gov', 'who.int', 'cdc.gov', 'fda.gov']) \
                             else 'medium' if link_domain == source_domain else 'low'
            
            # 创建新任务
            new_task = CrawlTask(
                url=url,
                protection_level=protection_level,
                metadata={
                    **metadata,
                    'depth': source_task.metadata.get('depth', 0) + 1  # 增加深度
                }
            )
            
            # 加入队列
            if self.priority_queue.enqueue(new_task, new_priority):
                added_count += 1
                
                # 限制每个源页面添加的最大链接数
                if added_count >= 100:  # 每个页面最多添加100个新链接
                    logger.info(f"已达到源页面最大链接提取数量(100): {source_url}")
                    break
        
        logger.info(f"从 {source_url} 提取并添加了 {added_count} 个新链接到队列")
    
    def _text_contains_medical_terms(self, text: str) -> bool:
        """检查文本是否包含医疗相关术语"""
        # 与_contains_medical_terms类似，但专用于链接文本分析
        medical_terms = [
            'clinical', '临床', 'trial', '试验', 'randomized', '随机',
            'patient', '患者', 'treatment', '治疗', 'disease', '疾病',
            'symptom', '症状', 'diagnosis', '诊断', 'prognosis', '预后',
            'medicine', '医学', 'therapy', '疗法', 'health', '健康',
            'medical', '医疗', 'doctor', '医生', 'hospital', '医院',
            'research', '研究', 'study', '研究', 'journal', '期刊'
        ]
        
        text = text.lower()
        return any(term.lower() in text for term in medical_terms)
    
    def _update_domain_stats(self, domain: str, task_record: Dict):
        """
        更新域名统计信息
        
        参数:
            domain: 域名
            task_record: 任务记录
        """
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {
                'success_count': 0,
                'fail_count': 0,
                'total_size': 0,
                'total_time': 0,
                'last_access': None,
                'avg_response_time': 0
            }
        
        stats = self.domain_stats[domain]
        
        # 更新访问时间
        stats['last_access'] = datetime.now().isoformat()
        
        # 计算任务执行时间
        if 'start_time' in task_record and 'end_time' in task_record:
            execution_time = task_record['end_time'] - task_record['start_time']
            stats['total_time'] += execution_time
            
            # 更新平均响应时间
            total_tasks = stats['success_count'] + stats['fail_count']
            if total_tasks > 0:
                stats['avg_response_time'] = stats['total_time'] / total_tasks
                
    def add_tasks(self, tasks: List[CrawlTask], priority: Optional[float] = None):
        """
        添加多个任务到队列
        
        参数:
            tasks: 任务列表
            priority: 可选的优先级（若不提供则使用任务自身优先级）
        
        返回:
            成功添加的任务数量
        """
        added_count = 0
        for task in tasks:
            task_priority = priority if priority is not None else task.priority
            if self.priority_queue.enqueue(task, task_priority):
                added_count += 1
        return added_count
    
    def get_stats(self) -> Dict:
        """
        获取调度器统计信息
        
        返回:
            包含调度器运行统计的字典
        """
        return {
            'active_tasks': len(self.active_tasks),
            'queue_size': self.priority_queue.size(),
            'domains_crawled': len(self.domain_stats),
            'total_success': sum(stats['success_count'] for stats in self.domain_stats.values()),
            'total_failed': sum(stats['fail_count'] for stats in self.domain_stats.values()),
            'total_size': sum(stats['total_size'] for stats in self.domain_stats.values() if 'total_size' in stats),
            'is_running': self.running
        }