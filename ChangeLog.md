# ChangeLog

## 2025.03.31

发现如下问题和可改进点：

- 页面刷新后会完全重置，需要刷新后保持页面内容，增加一个回到初始状态的按钮
- 联网搜索按钮功能不明确
- 反爬措施不完善
- 回复有时不是中文，需要修复
- 计划前搜索的功能可以不使用Tavily，使用输出处理的目标生产
  - Tavily报错：

  ```bash
  Tavily search returned malformed response: SSLError(MaxRetryError('HTTPSConnectionPool(host=\'api.tavily.com\', port=443): Max retries exceeded with url: /search (Caused by SSLError(SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, certificate is not valid for \'api.tavily.com\'. (_ssl.c:1010)")))'))

  ```
