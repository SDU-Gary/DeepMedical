"""
行为模拟器，用于生成精确的人类用户行为模式以避免被反爬虹扫系统检测。
主要功能：
1. 生成随机的页面滑动和点击行为
2. 模拟不同阅读速度和模式
3. 为不同类型的网站生成对应的行为策略
"""

import random
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse

class BehaviorSimulator:
    """
    行为模拟器类，用于模拟真实用户浏览行为
    支持根据不同网站类型和防护等级调整行为模式
    """
    def __init__(self):
        # 初始化基础行为模式
        self.scroll_patterns = [
            # [间隔时间, 每次滚动像素]
            [0.8, 300],   # 快速滚动
            [1.2, 500],   # 正常滚动
            [1.5, 800],   # 细读滚动
            [2.0, 1200],  # 非常细读
        ]
        
        self.click_patterns = [
            # [点击概率, 点击前停顶时间]
            [0.15, 1.0],   # 快速浏览，很少点击
            [0.25, 1.5],   # 正常浏览
            [0.40, 2.0],   # 感兴趣的浏览
            [0.60, 3.0],   # 细致浏览，大量点击
        ]
        
        # 医学页面专用行为模式 - 医学研究者模式
        self.medical_behavior = {
            "scroll_speed": [1.8, 500],  # 仔细阅读
            "pause_probability": 0.4,    # 频繁停顶阅读
            "pause_duration": [2.0, 8.0],  # 停顶时间较长
            "click_probability": 0.35,    # 中等点击率
            "hover_elements": ["figure", "table", ".abstract", ".methods", ".results", ".discussion"],
            "read_time_multiplier": 2.0,  # 阅读时间更长
        }
        
        # 新闻页面行为模式 - 快速浏览模式
        self.news_behavior = {
            "scroll_speed": [0.7, 700],  # 快速滚动
            "pause_probability": 0.1,    # 很少停顶
            "pause_duration": [0.5, 2.0],  # 停顶时间短
            "click_probability": 0.15,    # 低点击率
            "hover_elements": ["a.headline", ".thumbnail", ".news-item"],
            "read_time_multiplier": 0.6,  # 阅读时间短
        }
        
        # 电商页面行为模式 - 浏览商品模式
        self.ecommerce_behavior = {
            "scroll_speed": [1.0, 600],  # 中等滚动
            "pause_probability": 0.3,    # 有时停顶
            "pause_duration": [1.0, 3.0],  # 中等停顶时间
            "click_probability": 0.3,     # 中等点击率
            "hover_elements": ["img.product", ".price", ".rating", ".description"],
            "read_time_multiplier": 0.8,  # 阅读时间中等
        }
        
        # 学术页面行为模式 - 研究模式
        self.academic_behavior = {
            "scroll_speed": [2.0, 400],  # 慢速细读
            "pause_probability": 0.5,    # 频繁停顶
            "pause_duration": [3.0, 10.0],  # 停顶时间长
            "click_probability": 0.4,     # 中高点击率
            "hover_elements": ["cite", ".abstract", ".conclusion", ".reference", ".formula"],
            "read_time_multiplier": 2.5,  # 阅读时间很长
        }
        
        # 域名和行为模式映射
        self.domain_behavior_map = {
            # 医学网站
            "pubmed": "medical",
            "nih.gov": "medical",
            "nejm.org": "medical",
            "thelancet.com": "medical",
            "bmj.com": "medical",
            "mayo": "medical",
            "medscape": "medical",
            "webmd": "medical",
            "healthline": "medical",
            "medicalnewstoday": "medical",
            
            # 新闻网站
            "news": "news",
            "cnn": "news",
            "bbc": "news",
            "nytimes": "news",
            "washingtonpost": "news",
            "reuters": "news",
            "bloomberg": "news",
            
            # 学术网站
            "scholar": "academic",
            "sciencedirect": "academic",
            "researchgate": "academic",
            "academia.edu": "academic",
            "springer": "academic",
            "ieee": "academic",
            "arxiv": "academic",
            
            # 电商网站
            "amazon": "ecommerce",
            "alibaba": "ecommerce",
            "ebay": "ecommerce",
            "walmart": "ecommerce",
            "shop": "ecommerce",
            "store": "ecommerce",
        }
    
    async def generate_behavior(self, url: str, protection_level: str) -> Dict[str, Any]:
        """
        根据 URL 和防护等级生成行为策略
        
        参数:
            url: 目标网页的URL
            protection_level: 防护等级 (low, medium, high)
            
        返回:
            行为策略字典
        """
        # 解析网站类型
        behavior_type = self._get_behavior_type(url)
        
        # 生成基础行为
        behavior = await self._generate_base_behavior(behavior_type)
        
        # 根据防护等级调整行为
        behavior = self._adjust_for_protection_level(behavior, protection_level)
        
        # 为高防护网站添加随机性
        if protection_level == 'high':
            behavior = self._add_randomness(behavior)
            
        # 添加时间戳和唯一标识
        behavior["timestamp"] = datetime.now().isoformat()
        behavior["session_id"] = self._generate_session_id()
        
        return behavior
    
    def _get_behavior_type(self, url: str) -> str:
        """根据 URL 判断应使用的行为类型"""
        netloc = urlparse(url).netloc.lower()
        
        # 默认行为类型
        behavior_type = "general"
        
        # 检查域名是否匹配特定行为类型
        for domain, b_type in self.domain_behavior_map.items():
            if domain in netloc:
                behavior_type = b_type
                break
        
        # 检查 URL 路径中的关键词
        path = urlparse(url).path.lower()
        if behavior_type == "general":  # 如果域名没有匹配，则检查路径
            medical_keywords = ['health', 'clinic', 'disease', 'doctor', 'medicine', 'patient', 
                               'treatment', 'symptom', 'therapy', 'medical']
            academic_keywords = ['research', 'study', 'paper', 'article', 'journal', 'science', 
                              'abstract', 'publication', 'conference']
            news_keywords = ['news', 'article', 'blog', 'post', 'story', 'press', 'media', 'report']
            
            if any(keyword in path for keyword in medical_keywords):
                behavior_type = "medical"
            elif any(keyword in path for keyword in academic_keywords):
                behavior_type = "academic"
            elif any(keyword in path for keyword in news_keywords):
                behavior_type = "news"
        
        return behavior_type
    
    async def _generate_base_behavior(self, behavior_type: str) -> Dict[str, Any]:
        """生成特定行为类型的基础行为策略"""
        if behavior_type == "medical":
            base_behavior = self.medical_behavior.copy()
        elif behavior_type == "news":
            base_behavior = self.news_behavior.copy()
        elif behavior_type == "academic":
            base_behavior = self.academic_behavior.copy()
        elif behavior_type == "ecommerce":
            base_behavior = self.ecommerce_behavior.copy()
        else:  # general behavior
            # 随机选择一种滚动模式
            scroll_pattern = random.choice(self.scroll_patterns)
            # 随机选择一种点击模式
            click_pattern = random.choice(self.click_patterns)
            
            base_behavior = {
                "scroll_speed": scroll_pattern,
                "pause_probability": random.uniform(0.1, 0.3),
                "pause_duration": [random.uniform(0.5, 1.5), random.uniform(1.5, 4.0)],
                "click_probability": click_pattern[0],
                "hover_elements": ["a", "button", "input", "img", ".card", ".item"],
                "read_time_multiplier": random.uniform(0.8, 1.5),
            }
        
        # 生成随机化的页面交互序列
        interactions = await self._generate_interactions(base_behavior)
        base_behavior["interactions"] = interactions
        
        return base_behavior
    
    async def _generate_interactions(self, behavior: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成页面交互序列"""
        # 模拟一系列页面交互
        interactions = []
        num_interactions = random.randint(3, 10)
        
        for i in range(num_interactions):
            # 模拟滚动行为
            if i > 0:  # 第一个交互前先等待页面加载
                scroll_amt = int(random.uniform(300, 800) * behavior["scroll_speed"][1] / 500)
                interactions.append({
                    "type": "scroll",
                    "amount": scroll_amt,
                    "delay_before": random.uniform(behavior["scroll_speed"][0] * 0.8, behavior["scroll_speed"][0] * 1.2)
                })
            
            # 随机停顶
            if random.random() < behavior["pause_probability"]:
                pause_time = random.uniform(behavior["pause_duration"][0], behavior["pause_duration"][1])
                interactions.append({
                    "type": "wait",
                    "duration": pause_time
                })
            
            # 随机悬停
            if random.random() < 0.3:
                hover_elem = random.choice(behavior["hover_elements"])
                interactions.append({
                    "type": "hover",
                    "selector": hover_elem,
                    "duration": random.uniform(0.5, 2.0)
                })
            
            # 随机点击
            if random.random() < behavior["click_probability"]:
                click_elem = random.choice(behavior["hover_elements"])
                interactions.append({
                    "type": "click",
                    "selector": click_elem,
                    "delay_before": random.uniform(0.5, 1.5) 
                })
        
        return interactions
    
    def _adjust_for_protection_level(self, behavior: Dict[str, Any], protection_level: str) -> Dict[str, Any]:
        """根据防护等级调整行为策略"""
        if protection_level == "low":
            # 低防护级别不需要复杂行为
            return behavior
            
        elif protection_level == "medium":
            # 中等防护：增加随机性和更真实的行为
            behavior["mouse_tracks"] = True  # 添加鼠标跟踪
            behavior["pause_probability"] *= 1.2  # 增加停顶概率
            behavior["read_time_multiplier"] *= 1.3  # 增加阅读时间
            
            # 添加滚动跟踪
            behavior["scroll_tracking"] = {
                "variable_speed": True,
                "natural_acceleration": True,
                "jitter": random.uniform(5, 15)
            }
            
        elif protection_level == "high":
            # 高防护：最复杂的人类行为模拟
            behavior["mouse_tracks"] = True
            behavior["cursor_natural_movement"] = True  # 更自然的光标移动
            behavior["random_ui_interactions"] = True  # 随机 UI 交互
            behavior["emulate_focus_blur"] = True  # 模拟标签切换
            behavior["pause_probability"] *= 1.5
            behavior["read_time_multiplier"] *= 1.8
            
            # 高级滚动行为
            behavior["scroll_tracking"] = {
                "variable_speed": True,
                "natural_acceleration": True,
                "direction_changes": True,  # 偶尔向上滚动
                "jitter": random.uniform(10, 25),
                "read_pauses": True  # 阅读时的自然停顶
            }
            
            # 添加更多的交互
            behavior["interactions"].extend([
                {"type": "text_selection", "probability": 0.3},  # 随机选中文本
                {"type": "right_click", "probability": 0.1},   # 偶尔右击
                {"type": "browser_resize", "probability": 0.15}  # 偶尔调整浏览器大小
            ])
            
        return behavior
    
    def _add_randomness(self, behavior: Dict[str, Any]) -> Dict[str, Any]:
        """为行为策略添加随机性以增强回避反爬的能力"""
        # 添加用户特征分析回避
        jitter_factor = random.uniform(0.9, 1.1)
        for key in behavior.keys():
            if isinstance(behavior[key], (int, float)) and key != "timestamp":
                behavior[key] *= jitter_factor
        
        # 添加随机访问延迟
        behavior["initial_delay"] = random.uniform(0.5, 2.5)
        
        # 模拟网络延迟波动
        behavior["network_pattern"] = {
            "latency_range": [50, 150],  # 毫秒
            "jitter": random.uniform(5, 30),
            "bandwidth_variance": random.uniform(0.1, 0.3)
        }
        
        # 随机浏览器特征
        behavior["browser_fingerprint_noise"] = {
            "canvas_noise": random.random() < 0.7,
            "webgl_noise": random.random() < 0.6,
            "audio_noise": random.random() < 0.5
        }
        
        return behavior
    
    def _generate_session_id(self) -> str:
        """生成伪随机但可跟踪的会话 ID"""
        timestamp = int(time.time() * 1000)
        random_part = random.randint(1000000, 9999999)
        return f"session_{timestamp}_{random_part}"