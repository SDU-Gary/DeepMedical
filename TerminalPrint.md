```bash
2025-03-14 16:49:13,950 - root - WARNING - 使用模拟的DeepSeek API客户端，请安装真实客户端
2025-03-14 16:49:14,529 - root - WARNING - 使用模拟的DeepSeek API客户端，请安装真实客户端
2025-03-14 16:49:14,530 - target_generator - INFO - 目标池目录结构初始化成功
2025-03-14 16:49:14,530 - target_generator - INFO - 搜索缓存初始化: /home/kyrie/DeepMedical/input-service/data/search_cache
2025-03-14 16:49:14,539 - target_generator - INFO - 初始化DuckDuckGo搜索工具成功
2025-03-14 16:49:14,540 - __main__ - INFO - 初始化输入处理器

输入文本: 我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160

2025-03-14 16:49:14,540 - __main__ - INFO - 步骤1: URL检测和验证
2025-03-14 16:49:14,541 - __main__ - INFO - 步骤2: 意图分析
2025-03-14 16:49:14,542 - root - INFO - 模拟调用DeepSeek API: 你需要分析用户的输入, 并进行NLP分析. 用户输入如下：我想了解冠心病的最新治疗方法，特别是PCI...
2025-03-14 16:49:14,542 - __main__ - INFO - 步骤3: 目标生成
2025-03-14 16:49:14,542 - url_validator - INFO - [可达性检查] 开始检查: www.nejm.org
2025-03-14 16:49:14,997 - url_validator - WARNING - [可达性检查] 失败! URL: https://www.nejm.org/doi/full/10.1056/NEJMoa2034160, 状态码: 403
2025-03-14 16:49:15,998 - url_validator - INFO - [可达性检查] 尝试 2/3
2025-03-14 16:49:16,156 - url_validator - WARNING - [可达性检查] 失败! URL: https://www.nejm.org/doi/full/10.1056/NEJMoa2034160, 状态码: 403
2025-03-14 16:49:19,159 - url_validator - INFO - [可达性检查] 尝试 3/3
2025-03-14 16:49:19,357 - url_validator - WARNING - [可达性检查] 失败! URL: https://www.nejm.org/doi/full/10.1056/NEJMoa2034160, 状态码: 403
2025-03-14 16:49:19,358 - url_validator - WARNING - [可达性检查] 所有尝试均失败! URL: https://www.nejm.org/doi/full/10.1056/NEJMoa2034160
2025-03-14 16:49:19,358 - target_generator - INFO - 用户输入中检测到1个URL，其中0个有效，1个无效
2025-03-14 16:49:19,358 - target_generator - INFO - 开始进行搜索: 我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160
2025-03-14 16:49:19,358 - target_generator - INFO - 将使用搜索引擎: google, duckduckgo, arxiv
2025-03-14 16:49:19,358 - target_generator - INFO - 执行查询: 我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160
2025-03-14 16:49:19,358 - target_generator - INFO - 启动多引擎搜索: '我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160', 引擎: ['google', 'duckduckgo', 'arxiv']
2025-03-14 16:49:19,359 - target_generator - INFO - 使用缓存结果：google引擎的查询'我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160'
2025-03-14 16:49:19,359 - target_generator - INFO - 使用Google搜索缓存结果: 我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160
2025-03-14 16:49:19,359 - target_generator - INFO - 执行arXiv搜索: 我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160
2025-03-14 16:49:19,359 - arxiv - INFO - Requesting page (first: True, try: 0): https://export.arxiv.org/api/query?search_query=%E6%88%91%E6%83%B3%E4%BA%86%E8%A7%A3%E5%86%A0%E5%BF%83%E7%97%85%E7%9A%84%E6%9C%80%E6%96%B0%E6%B2%BB%E7%96%97%E6%96%B9%E6%B3%95%EF%BC%8C%E7%89%B9%E5%88%AB%E6%98%AFPCI%E6%89%8B%E6%9C%AF%E5%90%8E%E5%A6%82%E4%BD%95%E7%94%A8%E8%8D%AF+https%3A%2F%2Fwww.nejm.org%2Fdoi%2Ffull%2F10.1056%2FNEJMoa2034160&id_list=&sortBy=relevance&sortOrder=descending&start=0&max_results=100
2025-03-14 16:49:20,343 - primp - INFO - response: https://duckduckgo.com/?q=%E6%88%91%E6%83%B3%E4%BA%86%E8%A7%A3%E5%86%A0%E5%BF%83%E7%97%85%E7%9A%84%E6%9C%80%E6%96%B0%E6%B2%BB%E7%96%97%E6%96%B9%E6%B3%95%EF%BC%8C%E7%89%B9%E5%88%AB%E6%98%AFPCI%E6%89%8B%E6%9C%AF%E5%90%8E%E5%A6%82%E4%BD%95%E7%94%A8%E8%8D%AF+https%3A%2F%2Fwww.nejm.org%2Fdoi%2Ffull%2F10.1056%2FNEJMoa2034160 200
2025-03-14 16:49:20,723 - arxiv - INFO - Got empty first page; stopping generation
2025-03-14 16:49:21,748 - primp - INFO - response: https://duckduckgo.com/news.js?l=wt-wt&o=json&noamp=1&q=%E6%88%91%E6%83%B3%E4%BA%86%E8%A7%A3%E5%86%A0%E5%BF%83%E7%97%85%E7%9A%84%E6%9C%80%E6%96%B0%E6%B2%BB%E7%96%97%E6%96%B9%E6%B3%95%EF%BC%8C%E7%89%B9%E5%88%AB%E6%98%AFPCI%E6%89%8B%E6%9C%AF%E5%90%8E%E5%A6%82%E4%BD%95%E7%94%A8%E8%8D%AF+https%3A%2F%2Fwww.nejm.org%2Fdoi%2Ffull%2F10.1056%2FNEJMoa2034160&vqd=4-43613676832832416124758069378530244946&p=-1&df=y 200
2025-03-14 16:49:21,748 - target_generator - INFO - 各搜索引擎返回结果统计:
  - Google: 5个结果
2025-03-14 16:49:21,748 - target_generator - INFO - 统一搜索器共处理5个原始结果，返回5个去重结果
2025-03-14 16:49:21,748 - target_generator - INFO - 搜索器共返回5个结果
2025-03-14 16:49:21,749 - url_validator - INFO - [可达性检查] 开始检查: www.hanspub.org
2025-03-14 16:49:26,899 - url_validator - WARNING - [可达性检查] 超时! URL: https://www.hanspub.org/journal/paperinformation?paperid=52494, 超过5秒无响应
2025-03-14 16:49:27,901 - url_validator - INFO - [可达性检查] 尝试 2/3
2025-03-14 16:49:33,900 - url_validator - WARNING - [可达性检查] 超时! URL: https://www.hanspub.org/journal/paperinformation?paperid=52494, 超过5秒无响应
2025-03-14 16:49:36,903 - url_validator - INFO - [可达性检查] 尝试 3/3
2025-03-14 16:49:42,900 - url_validator - WARNING - [可达性检查] 超时! URL: https://www.hanspub.org/journal/paperinformation?paperid=52494, 超过5秒无响应
2025-03-14 16:49:42,900 - url_validator - WARNING - [可达性检查] 所有尝试均失败! URL: https://www.hanspub.org/journal/paperinformation?paperid=52494
2025-03-14 16:49:42,900 - url_validator - INFO - [可达性检查] 开始检查: www.lepumedical.com
2025-03-14 16:49:43,315 - url_validator - INFO - [可达性检查] 成功! 来源: www.lepumedical.com, 状态码: 200
2025-03-14 16:49:43,315 - url_validator - INFO - [可达性检查] 开始检查: www.wahh.com.cn
2025-03-14 16:49:43,420 - url_validator - WARNING - [可达性检查] 连接错误! URL: https://www.wahh.com.cn/Html/News/Articles/103218.html, 原因: Cannot connect to host www.wahh.com.cn:443 ssl:default [Connection reset by peer]
2025-03-14 16:49:44,421 - url_validator - INFO - [可达性检查] 尝试 2/3
2025-03-14 16:49:44,474 - url_validator - WARNING - [可达性检查] 连接错误! URL: https://www.wahh.com.cn/Html/News/Articles/103218.html, 原因: Cannot connect to host www.wahh.com.cn:443 ssl:default [Connection reset by peer]
2025-03-14 16:49:47,477 - url_validator - INFO - [可达性检查] 尝试 3/3
2025-03-14 16:49:47,529 - url_validator - WARNING - [可达性检查] 连接错误! URL: https://www.wahh.com.cn/Html/News/Articles/103218.html, 原因: Cannot connect to host www.wahh.com.cn:443 ssl:default [Connection reset by peer]
2025-03-14 16:49:47,529 - url_validator - WARNING - [可达性检查] 所有尝试均失败! URL: https://www.wahh.com.cn/Html/News/Articles/103218.html
2025-03-14 16:49:47,529 - url_validator - INFO - [可达性检查] 开始检查: www.google.com
2025-03-14 16:49:52,900 - url_validator - WARNING - [可达性检查] 超时! URL: https://www.google.com/search?num=12, 超过5秒无响应
2025-03-14 16:49:53,901 - url_validator - INFO - [可达性检查] 尝试 2/3
2025-03-14 16:49:59,897 - url_validator - WARNING - [可达性检查] 超时! URL: https://www.google.com/search?num=12, 超过5秒无响应
2025-03-14 16:50:02,900 - url_validator - INFO - [可达性检查] 尝试 3/3
2025-03-14 16:50:08,903 - url_validator - WARNING - [可达性检查] 超时! URL: https://www.google.com/search?num=12, 超过5秒无响应
2025-03-14 16:50:08,903 - url_validator - WARNING - [可达性检查] 所有尝试均失败! URL: https://www.google.com/search?num=12

处理结果:
{
    "raw_input": "我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160",
    "timestamp": "current_timestamp",
    "process_steps": [
        {
            "step": "url_validation",
            "detected_urls": [
                "https://www.nejm.org/doi/full/10.1056/NEJMoa2034160"
            ],
            "validated_urls": []
        },
        {
            "step": "intent_analysis",
            "intent_data": {
                "raw_text": "我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160",
                "entities": [
                    {
                        "text": "冠心病",
                        "start": 4,
                        "end": 7,
                        "standard_form": "冠状动脉粥样硬化性心脏病",
                        "type": "MEDICAL_TERM"
                    }
                ],
                "intent_analysis": {
                    "intent_class": "学术研究",
                    "key_terms": [
                        "冠心病",
                        "最新治疗方案"
                    ],
                    "temporal_constraint": "2023年至今"
                },
                "search_params": {
                    "precision": "high",
                    "recall": "medium"
                }
            }
        },
        {
            "step": "target_generation",
            "target_count": 0
        }
    ],
    "intent": {
        "raw_text": "我想了解冠心病的最新治疗方法，特别是PCI手术后如何用药 https://www.nejm.org/doi/full/10.1056/NEJMoa2034160",
        "entities": [
            {
                "text": "冠心病",
                "start": 4,
                "end": 7,
                "standard_form": "冠状动脉粥样硬化性心脏病",
                "type": "MEDICAL_TERM"
            }
        ],
        "intent_analysis": {
            "intent_class": "学术研究",
            "key_terms": [
                "冠心病",
                "最新治疗方案"
            ],
            "temporal_constraint": "2023年至今"
        },
        "search_params": {
            "precision": "high",
            "recall": "medium"
        }
    },
    "targets": [],
    "status": "success",
    "message": "处理成功"
}

```
