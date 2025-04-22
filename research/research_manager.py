"""
研究源管理器 - 负责管理和协调多个研究数据源的并行执行
"""

import asyncio
import logging
from typing import Dict, List, Any, Callable, Optional, Union
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ResearchSource(BaseModel):
    """研究数据源定义"""
    name: str  # 数据源名称
    description: str  # 数据源描述
    handler: Any  # 数据源处理函数，可以是同步或异步函数
    is_async: bool = False  # 是否为异步函数
    weight: float = 1.0  # 结果权重
    enabled: bool = True  # 是否启用
    
    # 允许任意类型，解决Pydantic无法处理Awaitable类型的问题
    model_config = {"arbitrary_types_allowed": True}

class ResearchResult(BaseModel):
    """研究结果模型"""
    source_name: str  # 来源名称
    content: str  # 结果内容
    success: bool = True  # 是否成功
    error_message: Optional[str] = None  # 错误信息
    
    def model_dump(self):
        """转换为字典，方便JSON序列化"""
        return {
            "source_name": self.source_name,
            "content": self.content,
            "success": self.success,
            "error_message": self.error_message
        }
    
    def __str__(self):
        """字符串表示"""
        return f"ResearchResult(source={self.source_name}, success={self.success})"

class ResearchManager:
    """研究源管理器，负责注册、执行和整合多个研究数据源"""
    
    def __init__(self):
        self.sources: Dict[str, ResearchSource] = {}
        logger.info("研究源管理器初始化完成")
    
    def register_source(self, source: ResearchSource) -> None:
        """
        注册一个研究数据源
        
        Args:
            source: 要注册的研究数据源
        """
        self.sources[source.name] = source
        logger.info(f"注册研究数据源: {source.name}")
    
    def enable_source(self, source_name: str) -> None:
        """启用指定的研究数据源"""
        if source_name in self.sources:
            self.sources[source_name].enabled = True
            logger.info(f"启用研究数据源: {source_name}")
    
    def disable_source(self, source_name: str) -> None:
        """禁用指定的研究数据源"""
        if source_name in self.sources:
            self.sources[source_name].enabled = False
            logger.info(f"禁用研究数据源: {source_name}")
    
    def get_enabled_sources(self) -> List[ResearchSource]:
        """获取所有启用的研究数据源"""
        return [source for source in self.sources.values() if source.enabled]
    
    async def _execute_async_source(self, source: ResearchSource, query: str, **kwargs) -> ResearchResult:
        """执行异步研究数据源"""
        try:
            content = await source.handler(query, **kwargs)
            return ResearchResult(
                source_name=source.name,
                content=content,
                success=True
            )
        except Exception as e:
            error_message = f"执行研究数据源 {source.name} 时出错: {str(e)}"
            logger.error(error_message)
            return ResearchResult(
                source_name=source.name,
                content="",
                success=False,
                error_message=error_message
            )
    
    async def _execute_sync_source(self, source: ResearchSource, query: str, **kwargs) -> ResearchResult:
        """在事件循环中执行同步研究数据源
        
        所有研究数据源都接收相同的完整参数集，在内部仅使用各自需要的参数
        """
        try:
            # 使用线程池执行同步函数，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            
            # 统一传递完整参数对象，在各函数内部只使用必要的参数
            content = await loop.run_in_executor(
                None, lambda: source.handler(query, **kwargs)
            )
            return ResearchResult(
                source_name=source.name,
                content=content,
                success=True
            )
        except Exception as e:
            error_message = f"执行研究数据源 {source.name} 时出错: {str(e)}"
            logger.error(error_message)
            return ResearchResult(
                source_name=source.name,
                content="",
                success=False,
                error_message=error_message
            )
    
    async def execute_source(self, source: ResearchSource, query: str, **kwargs) -> ResearchResult:
        """执行单个研究数据源并返回结果"""
        if source.is_async:
            return await self._execute_async_source(source, query, **kwargs)
        else:
            return await self._execute_sync_source(source, query, **kwargs)
    
    async def execute_all(self, query: str, **kwargs) -> List[ResearchResult]:
        """
        并行执行所有启用的研究数据源
        
        Args:
            query: 搜索查询
            **kwargs: 传递给各个研究数据源的额外参数
            
        Returns:
            各个数据源的研究结果列表
        """
        enabled_sources = self.get_enabled_sources()
        if not enabled_sources:
            logger.warning("没有启用的研究数据源")
            return []
        
        logger.info(f"开始并行执行 {len(enabled_sources)} 个研究数据源，查询: '{query}'")
        
        # 准备任务列表
        tasks = []
        for source in enabled_sources:
            if source.is_async:
                task = self._execute_async_source(source, query, **kwargs)
            else:
                task = self._execute_sync_source(source, query, **kwargs)
            tasks.append(task)
        
        # 并行执行所有任务
        results = await asyncio.gather(*tasks)
        
        logger.info(f"完成并行执行 {len(enabled_sources)} 个研究数据源")
        return results
        
    async def stream_execute_all(self, query: str, **kwargs):
        """
        流式并行执行所有启用的研究数据源
        
        Args:
            query: 搜索查询
            **kwargs: 传递给各个研究数据源的额外参数
            
        Yields:
            每个数据源完成时的研究结果
            以及可用于前端流式显示的中间状态信息
        """
        enabled_sources = self.get_enabled_sources()
        if not enabled_sources:
            logger.warning("没有启用的研究数据源")
            yield {
                "type": "research_status",
                "data": {
                    "status": "warning",
                    "message": "没有启用的研究数据源",
                }
            }
            # 在异步生成器中不能使用带值的return语句
            # 只能使用纯粹的return或者return None
            return
        
        # 创建一个完成结果列表
        completed_results = []
        
        # 初始状态通知
        yield {
            "type": "research_status",
            "data": {
                "status": "start", 
                "message": f"开始从{len(enabled_sources)}个数据源获取信息: {', '.join([s.name for s in enabled_sources])}"    
            }
        }
        
        # 创建Future对象列表
        tasks = {}
        for source in enabled_sources:
            # 创建一个直接传递给缓冲区的神经网络
            task = asyncio.create_task(self.execute_source(source, query, **kwargs))
            tasks[task] = source.name
            
            # 发送源启动通知
            yield {
                "type": "research_progress",
                "data": {
                    "source": source.name,
                    "status": "started",
                    "message": f"正在从{source.name}源获取数据...",
                    "progress": 0
                }
            }
        
        # 等待所有任务完成，但逻辑上每完成一个就可以返回一个结果
        pending = set(tasks.keys())
        while pending:
            # 等待任一完成的任务
            done, pending = await asyncio.wait(
                pending, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 处理完成的任务
            for done_task in done:
                source_name = tasks[done_task]
                try:
                    result = done_task.result()
                    completed_results.append(result)
                    
                    # 发送完成通知
                    if result.success:
                        message = f"数据源 {source_name} 完成搜索"
                        snippet = self._get_content_snippet(result.content, 100)  # 获取简短预览
                    else:
                        message = f"数据源 {source_name} 搜索失败: {result.error_message}"
                        snippet = ""
                    
                    yield {
                        "type": "research_progress",
                        "data": {
                            "source": source_name,
                            "status": "completed" if result.success else "failed",
                            "message": message,
                            "snippet": snippet,
                            "completed": len(completed_results),
                            "total": len(enabled_sources)
                        }
                    }
                    
                except Exception as e:
                    logger.error(f"处理研究数据源 {source_name} 结果时出错: {str(e)}")
                    error_result = ResearchResult(
                        source_name=source_name,
                        content="",
                        success=False,
                        error_message=f"处理结果时出错: {str(e)}"
                    )
                    completed_results.append(error_result)
                    
                    yield {
                        "type": "research_progress",
                        "data": {
                            "source": source_name,
                            "status": "error",
                            "message": f"处理结果时出错: {str(e)}",
                            "completed": len(completed_results),
                            "total": len(enabled_sources)
                        }
                    }
        
        # 所有任务完成，发送最终完成结果
        yield {
            "type": "research_status",
            "data": {
                "status": "complete",
                "message": f"完成所有{len(enabled_sources)}个数据源的搜索",
                "results": [result.model_dump() for result in completed_results]  # 返回可序列化的结果列表
            }
        }
        
        # 打印完成消息到标准输出
        print(f"研究结果总数: {len(completed_results)}")
        print(f"从{len(enabled_sources)}个数据源完成搜索: {', '.join([s.name for s in enabled_sources])}")
        
        logger.info(f"完成流式执行 {len(enabled_sources)} 个研究数据源")
        # 在异步生成器中不能使用带值的return
        # 修复语法错误：'return' with value in async generator
    
    def _get_content_snippet(self, content: str, max_length: int = 100) -> str:
        """从内容中提取简短预览"""
        if not content:
            return ""
        
        if len(content) <= max_length:
            return content
        
        return content[:max_length] + "..."
    
    def format_results(self, results: Union[List[ResearchResult], List[Dict]]) -> str:
        """
        将研究结果格式化为易于阅读的Markdown文本
        
        Args:
            results: 研究结果列表，可以是ResearchResult对象或已序列化的字典
            
        Returns:
            格式化的Markdown文本
        """
        if not results:
            return "没有获取到研究结果。"
        
        markdown = "# 医学信息研究报告\n\n"
        
        # 对结果进行分类，兼容对象和字典格式
        success_results = []
        failed_results = []
        
        for r in results:
            # 判断是否为ResearchResult对象或字典
            if isinstance(r, dict):
                # 已序列化的字典
                if r.get("success", True):
                    success_results.append(r)
                else:
                    failed_results.append(r)
            else:
                # ResearchResult对象
                if getattr(r, "success", True):
                    success_results.append(r)
                else:
                    failed_results.append(r)
        
        # 添加成功结果
        if success_results:
            for result in success_results:
                # 判断是字典还是对象
                if isinstance(result, dict):
                    source_name = result.get("source_name", "未知数据源")
                    content = result.get("content", "")
                else:
                    source_name = getattr(result, "source_name", "未知数据源")
                    content = getattr(result, "content", "")
                
                markdown += f"## {source_name} 搜索结果\n\n"
                markdown += f"{content}\n\n"
                markdown += "---\n\n"
        
        # 添加失败结果
        if failed_results:
            markdown += "## 未成功完成的数据源\n\n"
            for result in failed_results:
                # 判断是字典还是对象
                if isinstance(result, dict):
                    source_name = result.get("source_name", "未知数据源")
                    error_message = result.get("error_message", "未知错误")
                else:
                    source_name = getattr(result, "source_name", "未知数据源")
                    error_message = getattr(result, "error_message", "未知错误")
                    
                markdown += f"- **{source_name}**: {error_message}\n"
        
        return markdown


# 创建全局研究源管理器实例
research_manager = ResearchManager()
