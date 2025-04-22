# 项目文件结构

项目文件结构如下
```bash
├── api-gateway/            # API网关层 (新增)
│   ├── auth/               # 统一鉴权
│   └── routing/            # 请求路由到对应微服务
│
├── input-service/          # 输入处理微服务
│   ├── config/
│   │   ├── url_rules.yaml  # URL验证规则（对应C节点）
│   │   └── credibility.yaml # 可信度评估规则（M节点）
│   ├── src/
│   │   ├── url_validator.py      # URL有效性验证（C节点）
│   │   ├── intent_analyzer.py    # 意图分析（E节点）
│   │   └── target_generator.py   # 目标生成（J节点）
│   └── Dockerfile
│
├── crawler-service/         # 爬取调度微服务
│   ├── config/
│   │   ├── priority_rules.yaml # 动态优先级规则（O节点）
│   │   └── anti_crawler/      # 反爬策略配置目录（T/U/V节点）
│   ├── src/
│   │   ├── scheduler/        # 调度核心
│   │   │   ├── priority_queue.py # 优先级队列（O节点）
│   │   │   └── agent_dispatcher.py # Agent分发
│   │   ├── agents/
│   │   │   ├── playwright_agent/ # 高级采集（P节点）
│   │   │   └── scrapy_agent/    # 基础采集（Q节点）
│   │   └── anti_crawler/
│   │       ├── proxy_rotator.py # 代理IP轮换（T节点）
│   │       └── behavior_simulator.py # 行为模拟（V节点）
│   └── Dockerfile
│
├── processing-service/      # 数据处理微服务（新增分层）
│   ├── pipelines/          # 处理流水线
│   │   ├── cleaning/        # 清洗管道
│   │   │   ├── html_cleaner.py    # HTML清洗（Y节点）
│   │   │   └── sensitive_filter.py # 敏感过滤（A2节点）
│   │   └── enhancement/     # 增强管道
│   │       ├── schema_manager.py  # Schema对齐（AB节点）
│   │       └── evidence_builder.py # 证据链生成（AG节点）
│   ├── models/
│   │   └── knowledge_schema.py    # 动态Schema定义（AD节点）
│   └── Dockerfile
│
├── storage-service/         # 智能存储微服务（重大改进）
│   ├── gateway/             # 统一存储网关（AI节点）
│   │   ├── router.py        # 数据路由（AJ节点）
│   │   └── versioning.py    # 版本控制（AO节点）
│   ├── connectors/          # 存储引擎连接器
│   │   ├── neo4j_connector.py # 知识图谱存储（AK节点）
│   │   └── faiss_connector.py # 向量索引（AL节点）
│   └── Dockerfile
│
├── output-service/          # 输出微服务（新增交互层）
│   ├── templates/           # 报告模板
│   ├── src/
│   │   ├── query_parser/    # 查询解析引擎（AS节点）
│   │   │   ├── sparql_parser.py # 专家模式（AU节点）
│   │   │   └── nlq_parser.py    # 自然语言解析（AV节点）
│   │   └── visualization/   # 可视化组件
│   │       ├── echarts_render.py # 图谱渲染（AX节点）
│   │       └── drill_down.py     # 下钻分析（AY节点）
│   └── Dockerfile
│
├── libs/                    # 公共库（跨服务共享）
│   ├── deepseek-client/     # DeepSeek API客户端
│   │   └── api_wrapper.py   # 统一封装（所有API节点）
│   ├── data-models/         # 共享数据模型
│   │   ├── evidence.py      # 证据链模型（AH节点）
│   │   └── knowledge.py     # 知识图谱节点模型
│   └── logging/             # 统一日志配置
│
├── docker-compose.yml       # 微服务编排定义
└── helm-charts/             # Kubernetes部署配置（可选）
```
