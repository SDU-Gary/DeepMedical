"""
爬虫调度系统测试

测试AgentDispatcher、PlaywrightAgent和ScrapyAgent的功能。
该测试文件会初始化所有必要的组件，并执行一系列爬取任务。
"""

import sys
import os
import asyncio
import unittest
import logging
from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse

# 确保能够导入项目模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# 添加crawler-service路径
crawler_service_path = os.path.join(project_root, 'crawler-service')
sys.path.append(crawler_service_path)

# 导入待测试模块
from src.scheduler.agent_dispatcher import AgentDispatcher
from src.scheduler.priority_queue import PriorityQueue, CrawlTask
from src.agents.playwright_agent.agent import PlaywrightAgent
from src.agents.scrapy_agent.agent import ScrapyAgent
from src.anti_crawler.proxy_rotator import ProxyRotator
from src.anti_crawler.behavior_simulator import BehaviorSimulator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_agent_dispatcher")

# 测试结果处理器
class TestResultHandler:
    """测试用的结果处理器，记录爬取结果"""
    
    def __init__(self):
        self.results = []
        self.success_count = 0
        self.failure_count = 0
    
    async def process_result(self, task: CrawlTask, result: Dict[str, Any]):
        """处理爬取结果"""
        self.results.append({
            'url': task.url,
            'timestamp': datetime.now().isoformat(),
            'success': result.get('success', False),
            'content_length': len(result.get('content', '')),
            'title': result.get('title', ''),
            'extracted_links_count': len(result.get('extracted_links', []))
        })
        
        if result.get('success', False):
            self.success_count += 1
        else:
            self.failure_count += 1
            
        logger.info(f"处理结果: {task.url} - 成功: {result.get('success', False)}")
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "="*50)
        print(f"测试结果摘要:")
        print(f"总爬取URL数: {len(self.results)}")
        print(f"成功数: {self.success_count}")
        print(f"失败数: {self.failure_count}")
        print("="*50)
        
        if self.results:
            print("\n前5个爬取结果:")
            for i, result in enumerate(self.results[:5]):
                print(f"{i+1}. {result['url']} - 成功: {result['success']}, 内容长度: {result['content_length']}")
        print("="*50)

# 测试用的URL列表
TEST_URLS = [
    # 低防护静态页面 (适合ScrapyAgent)
    {"url": "https://www.sohu.com/", "priority": 50, "protection_level": "low"},
    {"url": "https://www.chinanews.com.cn/", "priority": 40, "protection_level": "low"},
    
    # 中等防护页面
    {"url": "https://www.zhihu.com/", "priority": 60, "protection_level": "medium"},
    {"url": "https://www.163.com/", "priority": 55, "protection_level": "medium"},
    
    # 高防护动态页面 (适合PlaywrightAgent)
    {"url": "https://www.jd.com/", "priority": 70, "protection_level": "high"},
    {"url": "https://www.taobao.com/", "priority": 75, "protection_level": "high"},
    
    # 医学相关网站 (高价值目标)
    {"url": "https://www.medsci.cn/", "priority": 85, "protection_level": "medium", 
     "metadata": {"title": "医学科学网 - 中国医疗科技资讯", "description": "医学临床试验和医学研究资料"}},
    {"url": "http://www.nhc.gov.cn/", "priority": 90, "protection_level": "medium",
     "metadata": {"title": "中华人民共和国国家卫生健康委员会", "description": "卫生健康政策法规"}}
]

async def run_test():
    """执行爬虫调度测试"""
    logger.info("初始化测试环境...")
    
    # 创建结果处理器
    result_handler = TestResultHandler()
    
    # 创建优先级队列并添加测试任务
    priority_queue = PriorityQueue()
    for url_info in TEST_URLS:
        task = CrawlTask(
            url=url_info["url"],
            priority=url_info["priority"],
            protection_level=url_info["protection_level"],
            metadata=url_info.get("metadata", {}),
            depth=0,
            retry_count=0
        )
        priority_queue.enqueue(task, task.priority)
    
    logger.info(f"已添加 {len(TEST_URLS)} 个测试URL到队列")
    
    # 初始化组件
    try:
        playwright_agent = PlaywrightAgent()
        scrapy_agent = ScrapyAgent()
        proxy_rotator = ProxyRotator()
        
        # 创建调度器
        dispatcher = AgentDispatcher(
            priority_queue=priority_queue,
            playwright_agent=playwright_agent,
            scrapy_agent=scrapy_agent,
            proxy_rotator=proxy_rotator,
            max_concurrent_tasks=3,  # 限制并发任务数以避免过载
            result_handler=result_handler
        )
        
        # 启动调度器
        logger.info("启动爬虫调度器...")
        await dispatcher.start()
        
        # 等待所有任务完成
        # 给予足够时间完成所有任务 (视网络情况可能需要调整)
        logger.info("等待任务完成...")
        wait_time = 60  # 等待60秒
        for i in range(wait_time):
            if priority_queue.is_empty() and not dispatcher.active_tasks:
                logger.info("所有任务已完成")
                break
            
            if i % 5 == 0:  # 每5秒打印一次状态
                active_count = len(dispatcher.active_tasks)
                queue_size = priority_queue.size()
                logger.info(f"状态: 活动任务 {active_count}, 队列中 {queue_size}")
            
            await asyncio.sleep(1)
        
        # 打印调度器统计信息
        logger.info("调度器统计信息:")
        stats = dispatcher.get_stats()
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        
        # 打印结果摘要
        result_handler.print_summary()
        
        # 停止调度器
        logger.info("停止调度器...")
        await dispatcher.stop()
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        raise
        
    logger.info("测试完成")

def main():
    """主函数"""
    print("开始爬虫调度系统测试...")
    
    # 运行测试
    asyncio.run(run_test())
    
    print("测试完成")

if __name__ == "__main__":
    main()
