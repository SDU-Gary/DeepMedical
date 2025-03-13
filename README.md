# DeepMedical - 智能医疗数据获取系统

基于DeepSeek API构建的智能医疗数据获取系统，旨在为医疗研究和临床决策提供高质量的信息资源。

## 项目概述

DeepMedical是一个专注于医疗领域的智能数据获取和分析系统，利用先进的自然语言处理技术，帮助用户快速获取、筛选和整合医学相关信息。系统能够理解用户的查询意图，识别医学专业术语，并从互联网上获取最相关的高质量医学资源。

### 核心特性

- **智能输入处理**：分析用户查询，识别医学实体和查询意图
- **URL智能验证**：自动检测、验证和评估URL的相关性
- **医学术语标准化**：将常见医学术语映射到标准化表达
- **目标资源生成**：基于查询意图生成高质量医学资源URL
- **异步并行处理**：高效处理多个URL和资源请求

## 系统架构

系统由以下微服务组成：

1. **输入处理服务**：处理用户输入，分析意图和实体
2. **数据获取服务**：根据分析结果获取相关医学数据
3. **内容处理服务**：处理和结构化获取的医学内容
4. **知识整合服务**：将处理后的内容整合为有价值的知识

## 输入处理服务详细说明

输入处理服务是整个系统的第一道关卡，负责理解用户需求并生成相应的数据获取目标。

### 主要组件

- **URL验证器**：验证URL的有效性和相关性
- **意图分析器**：使用DeepSeek API分析用户查询意图
- **目标生成器**：生成并管理数据获取目标

### 目录结构

```
input-service/
│
├── src/
│   ├── input_processor.py    # 主入口模块
│   ├── url_validator.py      # URL验证模块
│   ├── intent_analyzer.py    # 意图分析模块
│   └── target_generator.py   # 目标生成模块
│
├── config/
│   ├── url_rules.yaml        # URL验证规则配置
│   └── medical_terms.yaml    # 医学术语映射配置
│
└── data/
    ├── targets/              # 目标池存储目录
    └── index/                # 目标索引目录
```

## 安装与配置

### 环境要求

- Python 3.8+
- 相关依赖库

### 安装步骤

1. 克隆仓库
   ```
   git clone https://github.com/yourusername/DeepMedical.git
   cd DeepMedical
   ```

2. 安装依赖
   ```
   pip install -r requirements.txt
   ```

3. 配置环境变量
   ```
   export DEEPSEEK_API_KEY=your_api_key
   export DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1
   ```

## 使用示例

### 基本用法

```python
from input_service.src.input_processor import process_input

# 处理用户输入
result = process_input("我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药")
print(result)
```

### API服务

```python
from aiohttp import web
from input_service.src.input_processor import api_handler

async def handle_request(request):
    data = await request.json()
    result = await api_handler(data)
    return web.json_response(result)

app = web.Application()
app.router.add_post('/process', handle_request)
web.run_app(app, port=8080)
```

## 开发指南

### 添加新功能

1. 实现功能代码
2. 编写单元测试
3. 更新ChangeLog.md
4. 提交代码审核

### 代码风格

- 遵循PEP 8规范
- 使用类型注解
- 编写详细文档

## 贡献指南

我们欢迎各种形式的贡献，包括但不限于：

- 提交Bug报告
- 提出新功能建议
- 改进文档
- 提交代码

## 版本历史

详见[ChangeLog.md](./ChangeLog.md)

## 许可证

本项目采用MIT许可证，详情请查看LICENSE文件。

## 联系方式

- 项目维护者：[您的名字]
- 电子邮件：[您的邮箱]
