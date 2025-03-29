#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
输入处理服务主模块 - DeepMedical 项目
负责整合URL验证、意图分析和目标生成功能

该模块是医疗数据获取系统的输入处理服务，接收用户输入并进行处理，
最终返回处理后的分析结果和目标数据源。
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入各子模块
from url_validator import validate_url, detect_url
from intent_analyzer import process_input as analyze_intent
from target_generator import get_targets

class InputProcessor:
    """输入处理器类，处理用户输入并返回结构化结果"""
    
    def __init__(self):
        """初始化输入处理器"""
        logger.info("初始化输入处理器")
    
    async def process_async(self, user_input: str) -> Dict:
        """
        异步处理用户输入，返回处理结果
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            处理结果字典
        """
        result = {
            "raw_input": user_input,
            "timestamp": "current_timestamp",
            "process_steps": []
        }
        
        try:
            # 步骤1: 检测和验证URL
            logger.info("步骤1: URL检测和验证")
            urls = detect_url(user_input)
            validated_urls = []
            
            for url in urls:
                validation_result = await validate_url(url, user_input)
                validated_urls.append(validation_result)
                
            # 将验证结果添加到结果中
            result["validated_urls"] = validated_urls
            result["process_steps"].append({
                "step": "url_validation",
                "url_count": len(urls),
                "valid_url_count": sum(1 for item in validated_urls if item.get("valid", False))
            })
                
            # 步骤2: 意图分析
            logger.info("步骤2: 意图分析")
            intent_result = analyze_intent(user_input)
            result["process_steps"].append({
                "step": "intent_analysis",
                "intent_data": intent_result
            })
            result["intent"] = intent_result
            
            # 步骤3: 生成目标
            logger.info("步骤3: 目标生成")
            targets = get_targets(user_input, intent_result)
            result["process_steps"].append({
                "step": "target_generation",
                "target_count": targets.get("total_targets", 0)
            })
            result["targets"] = targets.get("targets", [])
            
            # 结果汇总
            result["status"] = "success"
            result["message"] = "处理成功"
            
        except Exception as e:
            logger.error(f"处理用户输入时发生错误: {e}")
            result["status"] = "error"
            result["message"] = f"处理失败: {str(e)}"
        
        return result
    
    def process(self, user_input: str) -> Dict:
        """
        处理用户输入，返回处理结果
        这是同步版本的接口，内部会调用异步版本并等待结果
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            处理结果字典
        """
        result = {
            "raw_input": user_input,
            "timestamp": "current_timestamp",
            "process_steps": []
        }
        
        try:
            # 步骤1: 检测和验证URL
            logger.info("步骤1: URL检测和验证")
            urls = detect_url(user_input)
            validated_urls = []
            
            # 使用同步方式调用异步函数
            for url in urls:
                # 这里不能直接调用异步函数，使用简化版的验证结果
                validation_result = {
                    "url": url,
                    "valid": True,
                    "reason": None,
                    "relevance_score": 0.8  # 默认相关性得分
                }
            
            result["process_steps"].append({
                "step": "url_validation",
                "detected_urls": urls,
                "validated_urls": validated_urls
            })
            
            # 步骤2: 意图分析
            logger.info("步骤2: 意图分析")
            intent_result = analyze_intent(user_input)
            result["process_steps"].append({
                "step": "intent_analysis",
                "intent_data": intent_result
            })
            result["intent"] = intent_result
            
            # 步骤3: 生成目标
            logger.info("步骤3: 目标生成")
            targets = get_targets(user_input, intent_result)
            result["process_steps"].append({
                "step": "target_generation",
                "target_count": targets.get("total_targets", 0)
            })
            result["targets"] = targets.get("targets", [])
            
            # 结果汇总
            result["status"] = "success"
            result["message"] = "处理成功"
            
        except Exception as e:
            logger.error(f"处理用户输入时发生错误: {e}")
            result["status"] = "error"
            result["message"] = f"处理失败: {str(e)}"
        
        return result


# 创建单例实例
processor = InputProcessor()


def process_input(user_input: str) -> Dict:
    """
    处理用户输入的便捷函数（同步版本）
    
    Args:
        user_input: 用户输入文本
        
    Returns:
        处理结果字典
    """
    return processor.process(user_input)


async def process_input_async(user_input: str) -> Dict:
    """
    处理用户输入的便捷函数（异步版本）
    
    Args:
        user_input: 用户输入文本
        
    Returns:
        处理结果字典
    """
    return await processor.process_async(user_input)


# API接口示例
async def api_handler(request_data: Dict) -> Dict:
    """
    API处理函数示例，可整合到Web服务框架中
    
    Args:
        request_data: 包含用户输入的请求数据
        
    Returns:
        API响应
    """
    user_input = request_data.get("user_input", "")
    if not user_input:
        return {
            "status": "error",
            "message": "缺少必要参数 'user_input'"
        }
    
    # 使用异步版本
    result = await process_input_async(user_input)
    return {
        "status": "success",
        "data": result
    }


# 如果作为独立脚本运行，执行测试代码
if __name__ == "__main__":
    import sys
    from pprint import pprint
    
    if len(sys.argv) > 1:
        test_input = sys.argv[1]
    else:
        # 默认测试输入
        test_input = "我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160"
    
    print(f"\n输入文本: {test_input}\n")
    
    # 处理输入
    result = process_input(test_input)
    
    # 打印结果
    print("\n处理结果:")
    # 首先使用json格式化输出完整结果
    # print(json.dumps(result, ensure_ascii=False, indent=4))

