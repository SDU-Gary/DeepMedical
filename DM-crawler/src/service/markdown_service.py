# src/service/markdown_service.py
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import logging
from typing import Dict
from fastapi.responses import FileResponse
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
import re


logger = logging.getLogger(__name__)


class MarkdownService:
    def __init__(self, output_dir: str = "output_markdowns"):
        self.output_dir = Path(output_dir)
        self._ensure_output_dir()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 配置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Markdown 输出目录: {self.output_dir.absolute()}")


    # 修改保存方法
    def save_article_as_markdown(self, request_data: dict) -> dict:
        try:
            # 强制使用处理后的文件名
            processed_name = self.sanitize_filename(request_data["filename"])
            content = request_data.get("content", "")

            final_filename = processed_name

            filepath = self.output_dir / final_filename

            # 写入文件（添加存在性检查）
            if filepath.exists():
                raise FileExistsError("文件已存在，请重命名")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "status": "success",
                "saved_filename": final_filename,  # 返回实际存储名
                "byte_size": len(content)
            }

        # =====================
        # 异常处理模块
        # =====================
        except FileNotFoundError as fnfe:
            self.logger.error(f"路径不存在: {str(fnfe)}")
            return {
                "status": "error",
                "message": "存储路径配置错误",
                "error_code": "PATH_NOT_FOUND"
            }
        except (IOError, OSError) as ioe:
            self.logger.error(f"文件系统错误: {str(ioe)}")
            return {
                "status": "error",
                "message": "文件保存失败，请检查存储空间",
                "error_code": "IO_ERROR"
            }
        except Exception as e:
            self.logger.error(f"未知错误: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": "系统内部错误",
                "error_code": "INTERNAL_ERROR"
            }

    # 在MarkdownService中添加安全校验
    def sanitize_filename(self, filename: str) -> str:
        """统一文件名处理规则"""
        # 先移除现有的 .md 扩展名
        base = re.sub(r'\.md$', '', filename.strip(), flags=re.IGNORECASE)
        # 清理非法字符并限制长度
        cleaned = re.sub(r'[^\w\u4e00-\u9fa5\-_.]', '_', base)
        cleaned = cleaned[:120].strip('_')
        cleaned = cleaned if cleaned else 'DM'
        # 添加 .md 扩展名
        return f"{cleaned}.md"

    def _extract_domain(self, url: str) -> str:
        """从URL提取域名"""
        domain = urlparse(url).netloc
        return domain.replace(".", "_") if domain else "unknown"

    def get_markdown_file(self, filename: str) -> FileResponse:
        # 1. 构建完整文件路径
        filepath = self.output_dir / filename

        # 2. 路径规范化处理
        resolved_path = filepath.resolve()

        # 3. 安全性校验（防止路径遍历攻击）
        if not resolved_path.is_relative_to(self.output_dir.resolve()):
            raise ValueError("非法文件路径")

        # 4. 文件存在性检查
        if not resolved_path.exists():
            raise FileNotFoundError(f"文件 {filename} 不存在")

        # 5. 文件类型校验
        if resolved_path.suffix.lower() != ".md":
            raise ValueError("仅支持下载Markdown文件")
            # 修正编码方式
        safe_filename = quote(filename, safe='')  # 核心修复点
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"
        }
        return FileResponse(
            filepath,
            media_type="text/markdown",
            headers=headers,
            filename=filename.encode('utf-8').decode('latin-1')
        )



