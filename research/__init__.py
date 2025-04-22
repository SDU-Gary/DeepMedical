"""
研究模块 - 提供并行执行多个研究数据源的能力
"""

# 先导入研究管理器

from .research_manager import ResearchManager, ResearchSource, ResearchResult, research_manager

# 导入研究源配置，这将执行数据源注册
# 注意：必须在创建了research_manager实例后才能导入

from . import sources

__all__ = [
    "ResearchManager",
    "ResearchSource", 
    "ResearchResult", 
    "research_manager",
    "sources"
]
