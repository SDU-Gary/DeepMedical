"""
提供将文本从一种语言翻译成另一种语言的工具，尤其是中文到英文的翻译
"""

import re
import logging
from typing import Annotated, Dict, Any
from langchain_core.tools import tool
from translate import Translator
from .decorators import log_io

# 初始化日志
logger = logging.getLogger(__name__)

# 初始化翻译器
translator = Translator(to_lang="en", from_lang="auto")

def is_chinese(text: str) -> bool:
    """
    检测文本中是否包含中文字符
    
    Args:
        text: 要检测的文本
        
    Returns:
        bool: 是否包含中文
    """
    return bool(re.search(r'[\u4e00-\u9fff]', text))

@tool
@log_io
def translate_tool(
    text: Annotated[str, "需要翻译的文本"],
    source_lang: Annotated[str, "源语言代码，如'zh'表示中文，或'auto'自动检测"] = "auto",
    target_lang: Annotated[str, "目标语言代码，如'en'表示英文"] = "en",
) -> Dict[str, Any]:
    """
    将文本从一种语言翻译成另一种语言，特别适合中文到英文的翻译。
    返回包含翻译结果的字典。
    """
    logger.debug(f"翻译工具收到请求: text='{text[:50]}...'")
    
    # 检查是否包含中文
    has_chinese = is_chinese(text)
    
    if not has_chinese and source_lang == "auto":
        # 如果未指定源语言且不包含中文，则直接返回原文
        return {
            "has_chinese": False,
            "original_text": text,
            "translated_text": text,
            "source_language": "unknown",
            "target_language": target_lang,
            "notes": "No Chinese characters detected, original text returned."
        }
    
    try:
        # 执行翻译
        if source_lang != "auto":
            # 如果指定了源语言，更新翻译器配置
            trans = Translator(to_lang=target_lang, from_lang=source_lang)
            translated_text = trans.translate(text)
        else:
            translated_text = translator.translate(text)
        
        # 返回结果
        return {
            "has_chinese": has_chinese,
            "original_text": text,
            "translated_text": translated_text,
            "source_language": "zh" if has_chinese else "unknown",
            "target_language": target_lang,
            "notes": "Translation successful."
        }
    except Exception as e:
        logger.error(f"翻译失败: {e}")
        return {
            "has_chinese": has_chinese,
            "original_text": text,
            "translated_text": text,  # 失败时返回原文
            "source_language": "zh" if has_chinese else "unknown",
            "target_language": target_lang,
            "notes": f"Translation failed: {str(e)}"
        }

# 导出工具
translate_tool = translate_tool
