#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
输入处理服务的单元测试
用于测试输入处理流水线的正确性
"""

import unittest
import sys
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# 将项目目录添加到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# 为源代码目录添加到路径
src_path = PROJECT_ROOT / 'input-service' / 'src'
sys.path.append(str(src_path))

# 直接导入模块
from input_processor import process_input, InputProcessor
from url_validator import detect_url, validate_url
from intent_analyzer import process_input as analyze_intent
from target_generator import get_targets


class TestInputProcessor(unittest.TestCase):
    """测试输入处理器"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建测试用例目录
        (PROJECT_ROOT / 'tests' / 'test_data').mkdir(exist_ok=True)
        
        # 模拟配置环境变量
        os.environ["DEEPSEEK_API_KEY"] = "test_api_key"
        os.environ["DEEPSEEK_ENDPOINT"] = "https://api.deepseek.com/v1"
        
        # 准备测试样例
        self.test_input_with_url = "我请你阅读这个网页的内容，并为我讲解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160"
        self.test_input_without_url = "我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药"

    def test_process_input_with_url(self):
        """测试处理包含URL的输入"""
        # 直接获取模块并模拟方法
        import input_processor
        import url_validator
        import intent_analyzer
        import target_generator
        
        # 保存原始方法
        original_validate_url = url_validator.validate_url
        original_analyze_intent = intent_analyzer.process_input
        original_get_targets = target_generator.get_targets
        
        try:
            # 设置模拟对象 - 注意使用AsyncMock模拟异步函数
            mock_validate_url = AsyncMock(return_value={
                "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa2034160",
                "is_valid": True,
                "reachable": True,
                "relevance_score": 0.8
            })
            url_validator.validate_url = mock_validate_url
            
            intent_analyzer.process_input = MagicMock(return_value={
                "raw_text": self.test_input_with_url,
                "entities": [
                    {"text": "冠心病", "standard_form": "冠状动脉粥样硬化性心脏病", "type": "MEDICAL_TERM"},
                    {"text": "PCI", "standard_form": "经皮冠状动脉介入术", "type": "MEDICAL_TERM"}
                ],
                "intent_analysis": {
                    "intent_class": "学术研究",
                    "key_terms": ["冠状动脉粥样硬化性心脏病", "经皮冠状动脉介入术", "抗凝治疗"],
                    "temporal_constraint": "当前"
                }
            })
            
            target_generator.get_targets = MagicMock(return_value={
                "targets": [
                    {
                        "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa2034160",
                        "source": "user_input",
                        "keywords": ["冠状动脉粥样硬化性心脏病", "经皮冠状动脉介入术", "抗凝治疗"]
                    },
                    {
                        "url": "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(23)00814-2/fulltext",
                        "source": "generated",
                        "keywords": ["冠状动脉粥样硬化性心脏病", "经皮冠状动脉介入术", "抗凝治疗"],
                        "relevance_score": 0.8
                    }
                ],
                "total_targets": 2
            })
            # 执行被测试函数
            result = process_input(self.test_input_with_url)
            
            # 验证结果
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["raw_input"], self.test_input_with_url)
            self.assertIn("intent", result)
            self.assertIn("targets", result)
            self.assertEqual(len(result["process_steps"]), 3)
            
            # 验证调用
            intent_analyzer.process_input.assert_called_once_with(self.test_input_with_url)
            target_generator.get_targets.assert_called_once()
        finally:
            # 恢复原始方法
            url_validator.validate_url = original_validate_url
            intent_analyzer.process_input = original_analyze_intent
            target_generator.get_targets = original_get_targets

    def test_process_input_without_url(self):
        """测试处理不包含URL的输入"""
        # 直接获取模块并模拟方法
        import input_processor
        import url_validator
        import intent_analyzer
        import target_generator
        
        # 保存原始方法
        original_validate_url = url_validator.validate_url
        original_analyze_intent = intent_analyzer.process_input
        original_get_targets = target_generator.get_targets
        
        try:
            # 设置模拟对象
            # 为validate_url设置异步模拟对象
            mock_validate_url = AsyncMock(return_value={
                "url": "https://example.com",
                "is_valid": True,
                "reachable": True,
                "relevance_score": 0.5
            })
            url_validator.validate_url = mock_validate_url
            
            intent_analyzer.process_input = MagicMock(return_value={
                "raw_text": self.test_input_without_url,
                "entities": [
                    {"text": "冠心病", "standard_form": "冠状动脉粥样硬化性心脏病", "type": "MEDICAL_TERM"},
                    {"text": "PCI", "standard_form": "经皮冠状动脉介入术", "type": "MEDICAL_TERM"}
                ],
                "intent_analysis": {
                    "intent_class": "学术研究",
                    "key_terms": ["冠状动脉粥样硬化性心脏病", "经皮冠状动脉介入术", "抗凝治疗"],
                    "temporal_constraint": "当前"
                }
            })
            
            target_generator.get_targets = MagicMock(return_value={
                "targets": [
                    {
                        "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa2034160",
                        "source": "generated",
                        "keywords": ["冠状动脉粥样硬化性心脏病", "经皮冠状动脉介入术", "抗凝治疗"],
                        "relevance_score": 0.85
                    }
                ],
                "total_targets": 1
            })
            # 执行被测试函数
            result = process_input(self.test_input_without_url)
            
            # 验证结果
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["raw_input"], self.test_input_without_url)
            self.assertIn("intent", result)
            self.assertIn("targets", result)
            
            # 验证调用
            intent_analyzer.process_input.assert_called_once_with(self.test_input_without_url)
            target_generator.get_targets.assert_called_once()
        finally:
            # 恢复原始方法
            url_validator.validate_url = original_validate_url
            intent_analyzer.process_input = original_analyze_intent
            target_generator.get_targets = original_get_targets

    def test_error_handling(self):
        """测试错误处理"""
        # 直接获取模块并模拟方法
        import input_processor
        import url_validator
        import intent_analyzer
        
        # 保存原始方法
        original_validate_url = url_validator.validate_url
        original_analyze_intent = intent_analyzer.process_input
        
        try:
            # 设置异步模拟对象
            url_validator.validate_url = AsyncMock(return_value={
                "url": "https://example.com",
                "is_valid": True,
                "reachable": True
            })
            # 设置模拟对象抛出异常
            intent_analyzer.process_input = MagicMock(side_effect=Exception("测试异常"))
            # 执行被测试函数
            result = process_input(self.test_input_without_url)
            
            # 验证错误处理
            self.assertEqual(result["status"], "error")
            self.assertIn("message", result)
            self.assertTrue(result["message"].startswith("处理失败"))
        finally:
            # 恢复原始方法
            url_validator.validate_url = original_validate_url
            intent_analyzer.process_input = original_analyze_intent

    def test_component_integration(self):
        """测试组件间的集成"""
        # 这个测试需要所有组件都正常工作，如果组件之间有问题，将会失败
        try:
            # 导入URL检测功能
            from url_validator import detect_url
            # 检测URL功能
            urls = detect_url(self.test_input_with_url)
            self.assertTrue(len(urls) > 0)
            self.assertEqual(urls[0], "https://www.nejm.org/doi/full/10.1056/NEJMoa2034160")
            
            # 注意: 完整流程测试需要配置异步环境
            # 我们可以在后续测试中使用asyncio来运行异步测试
            # asyncio.run(async_test_function())
            
            # 如果想测试完整的流程，取消下面的注释（可能会调用实际的API）
            # result = process_input(self.test_input_with_url)
            # self.assertEqual(result["status"], "success")
        except Exception as e:
            self.fail(f"集成测试失败: {e}")

    def tearDown(self):
        """测试后的清理工作"""
        # 清除环境变量
        if "DEEPSEEK_API_KEY" in os.environ:
            del os.environ["DEEPSEEK_API_KEY"]
        if "DEEPSEEK_ENDPOINT" in os.environ:
            del os.environ["DEEPSEEK_ENDPOINT"]


if __name__ == "__main__":
    unittest.main()
