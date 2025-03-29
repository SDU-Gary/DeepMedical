#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NLP意图分析模块 - 输入处理微服务的一部分
负责分析用户输入的意图，识别医学实体和查询性质
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import sys
import os

# 将libs目录添加到系统路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'libs'))

# 尝试导入DeepSeek客户端
try:
    from deepseek_client.api_wrapper import DeepSeekAPI
except ImportError:
    # 创建一个模拟的DeepSeek API类供讲解
    class DeepSeekAPI:
        def __init__(self, api_key=None, endpoint=None):
            self.api_key = api_key
            self.endpoint = endpoint
            logging.warning("使用模拟的DeepSeek API客户端，请安装真实客户端")
        
        def chat(self, prompt, system_prompt=None, temperature=0.7):
            logging.info(f"模拟调用DeepSeek API: {prompt[:50]}...")
            # 返回模拟的成功响应
            return json.dumps({
                "intent_class": "学术研究",
                "key_terms": ["冠心病", "最新治疗方案"],
                "temporal_constraint": "2023年至今"
            }, ensure_ascii=False)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载医学实体映射文件
def load_medical_mapping():
    """加载医学术语标准化映射"""
    mapping_file = Path(__file__).parent.parent / 'config' / 'medical_terms.yaml'
    
    if not mapping_file.exists():
        # 如果映射文件不存在，创建一个简单的示例文件
        basic_mapping = {
            # 疾病名称映射
            '心梗': '心肌梗死',
            '冠心病': '冠状动脉粥样硬化性心脏病',
            '糖尿病': '糖尿病',
            '高血压': '高血压病',
            
            '肺炎': '肺部感染',
            
            # 治疗方式映射
            'PCI': '经皮冠状动脉介入术',
            '支架': '冠状动脉支架植入术',
            '淌血序贴片': '血小板减少药物',
            'CABG': '冠状动脉旋转移植术',
            '局麻': '局部麻醉术',
            '全麻': '全身麻醉术',
        }
        
        # 写入默认配置
        with open(mapping_file, 'w', encoding='utf-8') as f:
            yaml.dump(basic_mapping, f, allow_unicode=True, default_flow_style=False)
        
        return basic_mapping
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"无法加载医学映射文件: {e}")
        return {}

# 全局变量
MEDICAL_MAPPING = load_medical_mapping()
DEEPSEEK_API = DeepSeekAPI()

def standardize_term(term: str) -> str:
    """将医学术语标准化，如将'心梗'映射到'心肌梦死'"""
    
    return MEDICAL_MAPPING.get(term, term)

def simple_medical_ner(text: str) -> List[Dict]:
    """
    简单的医学领域命名实体识别
    
    Args:
        text: 输入文本
    
    Returns:
        识别到的实体列表
    """
    entities = []
    
    # 基于映射字典的简单实体识别
    for term in MEDICAL_MAPPING.keys():
        # 使用边界匹配确保匹配完整词语
        pattern = r'\b' + re.escape(term) + r'\b' if re.match(r'^[a-zA-Z]+$', term) else term
        for match in re.finditer(pattern, text):
            start, end = match.span()
            entities.append({
                'text': term,
                'start': start,
                'end': end,
                'standard_form': standardize_term(term),
                'type': 'MEDICAL_TERM'
            })
    
    # 按照出现位置排序
    entities.sort(key=lambda x: x['start'])
    
    return entities

def analyze_intent(text: str) -> Dict:
    """
    分析用户输入的意图
    
    Args:
        text: 用户输入文本
    
    Returns:
        意图分析结果
    """
    # 步骤1：医疗领域实体识别
    entities = simple_medical_ner(text)
    
    # 提取主要关键词
    key_terms = [entity['standard_form'] for entity in entities]
    
    # 步骤2：调用DeepSeek API深度解析
    prompt = f"""你需要分析用户的输入, 并进行NLP分析. 用户输入如下：{text}
    
    请按以下JSON格式输出分析结果：
    {{
      "intent_class": ["学术研究"/"临床决策"/"商业需求"],
      "key_terms": ["冠心病", "最新治疗方案"],
      "temporal_constraint": "2023年至今"
    }}"""
    
    try:
        response = DEEPSEEK_API.chat(prompt)
        response_data = json.loads(response)
    except Exception as e:
        logger.error(f"DeepSeek API调用失败: {e}")
        # 失败时使用默认数据
        response_data = {
            "intent_class": "学术研究",  # 默认意图类别
            "key_terms": key_terms,     # 使用实体识别所得关键词
            "temporal_constraint": "当前"  # 默认时间限制
        }
    
    result = {
        "raw_text": text,
        "entities": entities,
        "intent_analysis": response_data
    }
    
    return result

# 配置DeepSeekAPI的连接参数
def configure_deepseek_api():
    """配置DeepSeek API的连接参数"""
    # 从环境变量获取API密钥和端点
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    endpoint = os.environ.get("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/v1")
    
    # 如果设置了环境变量，创建新的API实例
    if api_key:
        global DEEPSEEK_API
        DEEPSEEK_API = DeepSeekAPI(api_key=api_key, endpoint=endpoint)
        logger.info(f"已配置DeepSeek API连接到端点: {endpoint}")

# 在模块加载时调用配置函数
configure_deepseek_api()

# 入口函数，用于外部调用
def process_input(text: str) -> Dict:
    """
    处理用户输入并分析其意图
    
    Args:
        text: 用户输入文本
    
    Returns:
        包含意图分析结果的字典
    """
    intent_result = analyze_intent(text)
    
    # 根据分析意图进行额外处理
    intent_class = intent_result["intent_analysis"].get("intent_class", "")
    
    # 进行特定意图类型的处理
    if intent_class == "学术研究":
        # 为学术研究类型添加更高的精确度等级
        intent_result["search_params"] = {"precision": "high", "recall": "medium"}
    elif intent_class == "临床决策":
        # 为临床决策类型增加时效性权重
        intent_result["search_params"] = {"precision": "high", "recency": "high"}
    else:  # 商业需求或其他
        # 默认参数
        intent_result["search_params"] = {"precision": "medium", "recall": "high"}
    
    return intent_result

# 如果作为独立脚本运行，执行测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_text = sys.argv[1]
    else:
        # 默认测试文本
        test_text = "我想查找最新的冠心病治疗方案，特别是PCI手术后的抗凝管理"
    
    # 执行分析
    result = process_input(test_text)
    
    # 打印结果
    print(json.dumps(result, ensure_ascii=False, indent=2))