"""
代理轮换器，用于管理和轮换代理IP，是防止爬虫被封禁的关键组件。
主要功能：
1. 从多种源加载代理列表（文件、API、数据库）
2. 验证代理的可用性和性能
3. 基于目标网站和防护等级选择合适的代理
4. 根据代理性能和使用情况进行智能轮换
"""

import aiohttp
import asyncio
import random
import time
import logging
import json
import os
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
import yaml
import ipaddress

logger = logging.getLogger(__name__)

class ProxyInfo:
    """代理信息类，用于跟踪代理的状态和性能"""
    def __init__(self, proxy_url: str, source: str = "unknown", score: float = 5.0):
        self.proxy_url = proxy_url
        self.source = source
        self.score = score  # 1.0-10.0范围的评分，初始为5.0
        self.last_used = None
        self.last_checked = None
        self.success_count = 0
        self.fail_count = 0
        self.avg_response_time = None
        self.domains_used: Dict[str, dict] = {}  # domain -> {last_used, success_count, fail_count}
        self.status = "untested"  # untested, active, slow, failed
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "proxy_url": self.proxy_url,
            "source": self.source,
            "score": self.score,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "avg_response_time": self.avg_response_time,
            "domains_used": self.domains_used,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProxyInfo':
        """Create from dictionary"""
        proxy = cls(data["proxy_url"], data.get("source", "unknown"), data.get("score", 5.0))
        if data.get("last_used"):
            proxy.last_used = datetime.fromisoformat(data["last_used"])
        if data.get("last_checked"):
            proxy.last_checked = datetime.fromisoformat(data["last_checked"])
        proxy.success_count = data.get("success_count", 0)
        proxy.fail_count = data.get("fail_count", 0)
        proxy.avg_response_time = data.get("avg_response_time")
        proxy.domains_used = data.get("domains_used", {})
        proxy.status = data.get("status", "untested")
        return proxy

class ProxyRotator:
    """
    代理轮换器类，管理和选择合适的代理IP
    """
    def __init__(
        self,
        config_path: Optional[str] = None,
        proxy_list_file: Optional[str] = None,
        check_interval: int = 3600,  # 1小时检查一次代理可用性
        max_proxies: int = 100,
        minimum_score: float = 3.0
    ):
        self.config_path = config_path or os.path.expanduser("~/.config/deepmedical/proxy_config.yaml")
        self.proxy_list_file = proxy_list_file or os.path.expanduser("~/.config/deepmedical/proxies.json")
        self.check_interval = check_interval
        self.max_proxies = max_proxies
        self.minimum_score = minimum_score
        
        # 代理列表存储
        self.proxies: Dict[str, ProxyInfo] = {}  # proxy_url -> ProxyInfo
        self.domain_proxy_map: Dict[str, Set[str]] = {}  # domain -> set of proxy_urls
        
        # 时间跟踪
        self.last_reload = None
        self.last_check = None
        
        # 请求锁
        self._lock = asyncio.Lock()
        
        # 代理源配置
        self.proxy_sources = [
            {
                "name": "file",
                "type": "file",
                "path": self.proxy_list_file
            }
            # 可添加更多来源，如API和数据库
        ]
        
        # 默认代理
        self.default_proxy = None
        
        # 确保配置目录存在
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.proxy_list_file), exist_ok=True)
    
    async def initialize(self):
        """初始化代理轮换器"""
        # 加载配置
        await self._load_config()
        
        # 加载已保存的代理列表
        await self._load_proxies()
        
        # 如果代理列表为空或过期，则重新加载
        if not self.proxies or not self.last_reload or \
           (datetime.now() - self.last_reload > timedelta(hours=24)):
            await self._reload_proxies()
        
        # 启动定期检查代理可用性
        asyncio.create_task(self._check_proxies_periodically())
        
        logger.info(f"代理轮换器初始化完成，加载了 {len(self.proxies)} 个代理")
    
    async def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # 设置代理源
                if config and 'proxy_sources' in config:
                    self.proxy_sources = config['proxy_sources']
                
                # 设置其他配置项
                if config and 'settings' in config:
                    settings = config['settings']
                    if 'check_interval' in settings:
                        self.check_interval = settings['check_interval']
                    if 'max_proxies' in settings:
                        self.max_proxies = settings['max_proxies']
                    if 'minimum_score' in settings:
                        self.minimum_score = settings['minimum_score']
                    if 'default_proxy' in settings:
                        self.default_proxy = settings['default_proxy']
                
                logger.info(f"已成功加载代理配置文件: {self.config_path}")
            else:
                # 创建默认配置
                default_config = {
                    'proxy_sources': self.proxy_sources,
                    'settings': {
                        'check_interval': self.check_interval,
                        'max_proxies': self.max_proxies,
                        'minimum_score': self.minimum_score,
                        'default_proxy': self.default_proxy
                    }
                }
                
                # 将默认配置写入文件
                with open(self.config_path, 'w') as f:
                    yaml.dump(default_config, f, default_flow_style=False)
                
                logger.info(f"创建了默认代理配置文件: {self.config_path}")
        except Exception as e:
            logger.error(f"加载代理配置失败: {str(e)}")
    
    async def _load_proxies(self):
        """从文件中加载已保存的代理列表"""
        try:
            if os.path.exists(self.proxy_list_file):
                with open(self.proxy_list_file, 'r') as f:
                    data = json.load(f)
                
                if 'proxies' in data:
                    # 加载代理信息
                    for proxy_data in data['proxies']:
                        proxy_info = ProxyInfo.from_dict(proxy_data)
                        self.proxies[proxy_info.proxy_url] = proxy_info
                
                if 'domain_proxy_map' in data:
                    # 加载域名代理映射
                    for domain, proxy_urls in data['domain_proxy_map'].items():
                        self.domain_proxy_map[domain] = set(proxy_urls)
                
                if 'last_reload' in data and data['last_reload']:
                    self.last_reload = datetime.fromisoformat(data['last_reload'])
                
                if 'last_check' in data and data['last_check']:
                    self.last_check = datetime.fromisoformat(data['last_check'])
                
                logger.info(f"从 {self.proxy_list_file} 加载了 {len(self.proxies)} 个代理")
            else:
                logger.info(f"代理列表文件不存在: {self.proxy_list_file}")
        except Exception as e:
            logger.error(f"加载代理列表失败: {str(e)}")
            
    async def _save_proxies(self):
        """将代理信息保存到文件"""
        try:
            # 准备保存数据
            data = {
                'proxies': [proxy_info.to_dict() for proxy_info in self.proxies.values()],
                'domain_proxy_map': {domain: list(proxy_urls) for domain, proxy_urls in self.domain_proxy_map.items()},
                'last_reload': self.last_reload.isoformat() if self.last_reload else None,
                'last_check': self.last_check.isoformat() if self.last_check else None
            }
            
            # 写入文件
            with open(self.proxy_list_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"代理列表已保存到 {self.proxy_list_file}")
        except Exception as e:
            logger.error(f"保存代理列表失败: {str(e)}")
    
    async def _reload_proxies(self):
        """从多个源重新加载代理列表"""
        async with self._lock:
            try:
                # 保留现有的活跃代理
                active_proxies = {}
                for proxy_url, proxy_info in self.proxies.items():
                    if proxy_info.status != "failed" and proxy_info.score >= self.minimum_score:
                        active_proxies[proxy_url] = proxy_info
                
                # 清空代理列表
                self.proxies.clear()
                
                # 先加回活跃的代理
                for proxy_url, proxy_info in active_proxies.items():
                    self.proxies[proxy_url] = proxy_info
                
                # 从每个配置的源加载代理
                for source in self.proxy_sources:
                    try:
                        if source["type"] == "file":
                            await self._load_proxies_from_file(source["path"], source["name"])
                        elif source["type"] == "api":
                            await self._load_proxies_from_api(source["url"], source["name"])
                        elif source["type"] == "database":
                            await self._load_proxies_from_database(source["connection"], source["name"])
                    except Exception as e:
                        logger.error(f"从源 {source['name']} 加载代理失败: {str(e)}")
                
                # 设置重新加载时间
                self.last_reload = datetime.now()
                
                # 限制代理总数
                if len(self.proxies) > self.max_proxies:
                    # 按评分排序并只保留最高的N个
                    sorted_proxies = sorted(
                        self.proxies.items(),
                        key=lambda x: x[1].score,
                        reverse=True
                    )
                    
                    # 重新构建代理列表
                    self.proxies = {url: info for url, info in sorted_proxies[:self.max_proxies]}
                
                # 保存更新后的代理列表
                await self._save_proxies()
                
                logger.info(f"重新加载代理成功，当前共有 {len(self.proxies)} 个代理")
            except Exception as e:
                logger.error(f"重新加载代理失败: {str(e)}")
    
    async def _load_proxies_from_file(self, file_path: str, source_name: str):
        """从文本文件加载代理列表"""
        if not os.path.exists(file_path):
            logger.warning(f"代理文件不存在: {file_path}")
            return
            
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # 支持多种文件格式
            if file_path.endswith('.json'):
                # JSON格式尝试解析
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        proxy_list = data
                    elif isinstance(data, dict) and 'proxies' in data:
                        proxy_list = data['proxies']
                    else:
                        proxy_list = [data]
                        
                    # 添加代理
                    for proxy_item in proxy_list:
                        if isinstance(proxy_item, str):
                            self._add_proxy(proxy_item, source_name)
                        elif isinstance(proxy_item, dict) and 'url' in proxy_item:
                            self._add_proxy(proxy_item['url'], source_name)
                except json.JSONDecodeError:
                    # 不是JSON格式，当作文本处理
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self._add_proxy(line, source_name)
            else:
                # 文本格式，每行一个代理
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self._add_proxy(line, source_name)
        except Exception as e:
            logger.error(f"从文件 {file_path} 加载代理失败: {str(e)}")
    
    async def _load_proxies_from_api(self, api_url: str, source_name: str):
        """从 API 加载代理列表"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 解析不同的API响应格式
                        proxy_list = []
                        if isinstance(data, list):
                            proxy_list = data
                        elif isinstance(data, dict):
                            if 'data' in data and isinstance(data['data'], list):
                                proxy_list = data['data']
                            elif 'proxies' in data and isinstance(data['proxies'], list):
                                proxy_list = data['proxies']
                            elif 'result' in data and isinstance(data['result'], list):
                                proxy_list = data['result']
                        
                        # 处理代理列表
                        for proxy_item in proxy_list:
                            if isinstance(proxy_item, str):
                                self._add_proxy(proxy_item, source_name)
                            elif isinstance(proxy_item, dict):
                                # 不同API的不同字段名
                                proxy_url = None
                                for field in ['url', 'proxy', 'proxy_url', 'address', 'ip']:
                                    if field in proxy_item:
                                        if field == 'ip' and 'port' in proxy_item:
                                            # 如果是IP和端口分开的，需要组合
                                            ip = proxy_item['ip']
                                            port = proxy_item['port']
                                            proxy_url = f"http://{ip}:{port}"
                                        else:
                                            proxy_url = proxy_item[field]
                                        break
                                
                                if proxy_url:
                                    self._add_proxy(proxy_url, source_name)
                    else:
                        logger.warning(f"API请求失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"从 API {api_url} 加载代理失败: {str(e)}")
    
    async def _load_proxies_from_database(self, connection_info: dict, source_name: str):
        """从数据库加载代理列表（占位函数，实际实现将基于数据库类型）"""
        # 实际实现时会根据不同数据库连接和查询逻辑具体实现
        # 这里只是一个占位示例
        logger.info(f"数据库代理源加载未实现: {source_name}")
    
    def _add_proxy(self, proxy_url: str, source: str):
        """添加代理到列表中"""
        # 检查代理URL格式
        if not self._validate_proxy_format(proxy_url):
            return
            
        # 如果代理已存在，更新信息
        if proxy_url in self.proxies:
            return
            
        # 创建新的代理信息
        proxy_info = ProxyInfo(proxy_url, source)
        self.proxies[proxy_url] = proxy_info
    
    def _validate_proxy_format(self, proxy_url: str) -> bool:
        """验证代理URL格式"""
        # 基本格式检查
        if not proxy_url or not isinstance(proxy_url, str):
            return False
            
        # 检查是否含有协议前缀
        if not (proxy_url.startswith('http://') or proxy_url.startswith('https://') or 
                proxy_url.startswith('socks4://') or proxy_url.startswith('socks5://')):
            # 尝试添加默认http前缀
            proxy_url = f"http://{proxy_url}"
        
        # 检查URL格式
        try:
            parsed = urlparse(proxy_url)
            # 检查是否有域名/IP和端口
            if not parsed.netloc:
                return False
                
            # 如果是IP地址，检查是否有效
            host_part = parsed.netloc.split(':')[0]
            try:
                ipaddress.ip_address(host_part)
                # 是有效的IP地址
            except ValueError:
                # 不是IP地址，可能是域名
                pass
                
            return True
        except Exception:
            return False
            
    async def _check_proxies_periodically(self):
        """定期检查代理的可用性"""
        while True:
            try:
                # 等待一段时间
                await asyncio.sleep(self.check_interval)
                
                logger.info("开始定期检查代理可用性...")
                await self._check_all_proxies()
                
                # 更新检查时间
                self.last_check = datetime.now()
                
                # 保存更新后的代理状态
                await self._save_proxies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定期检查代理失败: {str(e)}")
                await asyncio.sleep(60)  # 遇到错误等待一分钟再重试
    
    async def _check_all_proxies(self):
        """检查所有代理的可用性"""
        async with self._lock:
            # 使用多个测试URL
            test_urls = [
                "https://www.google.com",
                "https://www.baidu.com",
                "https://www.github.com",
                "https://www.example.com"
            ]
            
            # 每次随机选择一个测试URL
            test_url = random.choice(test_urls)
            
            # 创建任务列表
            tasks = []
            for proxy_url in list(self.proxies.keys()):
                tasks.append(self._check_proxy(proxy_url, test_url))
            
            # 限制并发量，分批检查
            batch_size = 10
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i+batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
            
            # 清理失效的代理
            to_remove = [proxy_url for proxy_url, info in self.proxies.items() 
                         if info.status == "failed" and info.score < self.minimum_score / 2]
            
            for proxy_url in to_remove:
                del self.proxies[proxy_url]
                # 同时清理域名映射中的该代理
                for domain, proxy_set in self.domain_proxy_map.items():
                    if proxy_url in proxy_set:
                        proxy_set.remove(proxy_url)
            
            # 如果可用代理数量太少，尝试重新加载
            active_count = sum(1 for info in self.proxies.values() if info.status != "failed")
            if active_count < max(5, self.max_proxies * 0.2):  # 小于20%或小于5个
                logger.warning(f"可用代理数量过少 ({active_count})，重新加载代理")
                await self._reload_proxies()
            
            logger.info(f"代理检查完成，当前有 {active_count} 个活跃代理，共 {len(self.proxies)} 个代理")
    
    async def _check_proxy(self, proxy_url: str, test_url: str):
        """检查单个代理的可用性"""
        if proxy_url not in self.proxies:
            return
            
        proxy_info = self.proxies[proxy_url]
        timeout = aiohttp.ClientTimeout(total=10)  # 10秒超时
        
        try:
            start_time = time.time()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(test_url, proxy=proxy_url, ssl=False) as response:
                    # 计算响应时间
                    response_time = time.time() - start_time
                    
                    # 检查是否成功
                    if 200 <= response.status < 300:
                        # 更新代理状态
                        proxy_info.last_checked = datetime.now()
                        proxy_info.success_count += 1
                        
                        # 计算平均响应时间
                        if proxy_info.avg_response_time is None:
                            proxy_info.avg_response_time = response_time
                        else:
                            proxy_info.avg_response_time = 0.7 * proxy_info.avg_response_time + 0.3 * response_time
                        
                        # 更新评分和状态
                        proxy_info.score = min(10.0, proxy_info.score + 0.2)
                        
                        if proxy_info.avg_response_time > 5.0:
                            proxy_info.status = "slow"
                        else:
                            proxy_info.status = "active"
                            
                        logger.debug(f"代理 {proxy_url} 检查成功，响应时间: {response_time:.2f}s, 评分: {proxy_info.score:.1f}")
                    else:
                        # HTTP错误状态码
                        proxy_info.fail_count += 1
                        proxy_info.score = max(0.0, proxy_info.score - 0.5)
                        
                        if proxy_info.score < self.minimum_score:
                            proxy_info.status = "failed"
                            
                        logger.debug(f"代理 {proxy_url} 返回错误状态码: {response.status}, 评分: {proxy_info.score:.1f}")
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            # 连接错误或超时
            proxy_info.fail_count += 1
            proxy_info.score = max(0.0, proxy_info.score - 1.0)  # 连接错误扣分更多
            
            if proxy_info.score < self.minimum_score:
                proxy_info.status = "failed"
                
            logger.debug(f"代理 {proxy_url} 检查失败: {str(e)}, 评分: {proxy_info.score:.1f}")
        except Exception as e:
            # 其他错误
            proxy_info.fail_count += 1
            proxy_info.score = max(0.0, proxy_info.score - 0.7)
            
            if proxy_info.score < self.minimum_score:
                proxy_info.status = "failed"
                
            logger.debug(f"代理 {proxy_url} 检查发生异常: {str(e)}, 评分: {proxy_info.score:.1f}")
    
    async def get_proxy(self, domain: str, protection_level: str = "medium") -> Optional[str]:
        """
        获取特定域名的代理
        
        参数:
            domain: 目标域名
            protection_level: 防护等级 (low, medium, high)
            
        返回:
            代理URL字符串或None
        """
        async with self._lock:
            # 低防护网站不需要代理
            if protection_level == "low" and random.random() < 0.7:
                return None
                
            # 获取合适的代理
            proxy_url = await self._select_proxy_for_domain(domain, protection_level)
            
            if proxy_url:
                # 更新代理使用情况
                proxy_info = self.proxies[proxy_url]
                proxy_info.last_used = datetime.now()
                
                # 更新域名使用情况
                if domain not in proxy_info.domains_used:
                    proxy_info.domains_used[domain] = {
                        "last_used": datetime.now().isoformat(),
                        "success_count": 0,
                        "fail_count": 0
                    }
                else:
                    proxy_info.domains_used[domain]["last_used"] = datetime.now().isoformat()
                
                logger.debug(f"为 {domain} 选择代理: {proxy_url}")
                return proxy_url
            
            # 如果没有合适的代理，则返回默认代理或None
            logger.warning(f"没有找到 {domain} 的合适代理")
            return self.default_proxy
    
    async def update_proxy_status(self, proxy_url: str, domain: str, success: bool, response_time: Optional[float] = None):
        """
        更新代理的状态和评分
        
        参数:
            proxy_url: 代理URL
            domain: 使用的域名
            success: 是否成功
            response_time: 响应时间（秒）
        """
        if not proxy_url or proxy_url not in self.proxies:
            return
            
        async with self._lock:
            proxy_info = self.proxies[proxy_url]
            
            # 更新成功/失败计数
            if success:
                proxy_info.success_count += 1
                if domain in proxy_info.domains_used:
                    proxy_info.domains_used[domain]["success_count"] += 1
                # 成功时小幅度提高评分
                proxy_info.score = min(10.0, proxy_info.score + 0.1)
            else:
                proxy_info.fail_count += 1
                if domain in proxy_info.domains_used:
                    proxy_info.domains_used[domain]["fail_count"] += 1
                # 失败时显著降低评分
                proxy_info.score = max(0.0, proxy_info.score - 0.5)
            
            # 更新平均响应时间
            if response_time is not None:
                if proxy_info.avg_response_time is None:
                    proxy_info.avg_response_time = response_time
                else:
                    # 加权平均，新的数据占比更高
                    proxy_info.avg_response_time = 0.3 * response_time + 0.7 * proxy_info.avg_response_time
            
            # 更新状态
            if proxy_info.score < self.minimum_score:
                proxy_info.status = "failed"
            elif proxy_info.avg_response_time and proxy_info.avg_response_time > 5.0:
                proxy_info.status = "slow"
            else:
                proxy_info.status = "active"
            
            # 设置检查时间
            proxy_info.last_checked = datetime.now()
            
            # 定期保存代理状态
            if random.random() < 0.05:  # 5%的概率进行保存，避免频繁IO
                await self._save_proxies()
    
    async def _select_proxy_for_domain(self, domain: str, protection_level: str) -> Optional[str]:
        """为特定域名选择合适的代理"""
        if not self.proxies:
            return None
        
        # 针对特定域名的代理列表检查
        domain_specific_proxies = set()
        if domain in self.domain_proxy_map:
            domain_specific_proxies = self.domain_proxy_map[domain].copy()
        
        # 根据防护等级设置最低要求
        min_score_requirement = self.minimum_score  # 基础要求
        if protection_level == "high":
            min_score_requirement = max(6.0, min_score_requirement)  # 高防护网站需要更高的代理分数
        
        suitable_proxies = []
        
        # 策略：优先尝试采用针对该域名表现良好的代理
        if domain_specific_proxies:
            for proxy_url in domain_specific_proxies:
                if proxy_url in self.proxies:
                    proxy_info = self.proxies[proxy_url]
                    # 选择活跃且评分足够高的代理
                    if proxy_info.status != "failed" and proxy_info.score >= min_score_requirement:
                        domain_data = proxy_info.domains_used.get(domain, {})
                        success_rate = 0
                        if domain_data:
                            total = domain_data.get("success_count", 0) + domain_data.get("fail_count", 0)
                            if total > 0:
                                success_rate = domain_data.get("success_count", 0) / total
                        
                        # 成功率大于50%的代理加入候选
                        if success_rate >= 0.5 or total == 0:
                            suitable_proxies.append((proxy_url, proxy_info.score, success_rate))
        
        # 如果没有适合的域名特定代理，选择所有活跃代理
        if not suitable_proxies:
            for proxy_url, proxy_info in self.proxies.items():
                if proxy_info.status != "failed" and proxy_info.score >= min_score_requirement:
                    suitable_proxies.append((proxy_url, proxy_info.score, 0))
        
        if not suitable_proxies:
            return None
        
        # 按评分和成功率排序
        suitable_proxies.sort(key=lambda x: (x[2], x[1]), reverse=True)
        
        # 加权随机选择，评分越高、成功率越高的代理被选中概率越大
        weights = [0.5 + 0.5 * (score / 10) + 0.5 * success_rate for _, score, success_rate in suitable_proxies]
        
        # 添加随机性，防止固定模式
        if random.random() < 0.1 and len(suitable_proxies) > 1:  # 10%的概率纯随机选择
            return suitable_proxies[random.randint(0, len(suitable_proxies) - 1)][0]
        
        # 加权随机选择
        try:
            selected_proxy = random.choices(
                [p[0] for p in suitable_proxies],
                weights=weights,
                k=1
            )[0]
            
            # 更新域名代理映射
            if domain not in self.domain_proxy_map:
                self.domain_proxy_map[domain] = set()
            self.domain_proxy_map[domain].add(selected_proxy)
            
            return selected_proxy
        except (ValueError, IndexError):
            # 如果加权选择失败，选择列表中的第一个代理
            if suitable_proxies:
                return suitable_proxies[0][0]
            return None