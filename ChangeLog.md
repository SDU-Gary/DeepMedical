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

                    try:
                        output_data = data.get("output")
                        messages_to_save = []

                        if isinstance(output_data, dict) and output_data.get("messages"):
                            messages_to_save = output_data["messages"]
                        elif hasattr(output_data, "update") and isinstance(output_data.update, dict) and output_data.update.get("messages"):
                            # 如果是Command对象
                            messages_to_save = output_data.update["messages"]

                        if messages_to_save and len(messages_to_save) > 0:
                            last_message_obj = messages_to_save[-1]  # LangChain消息对象
                            # logger.info(f"Last message object for {name}: {last_message_obj}")

                            message_content_to_save = None
                            if hasattr(last_message_obj, "content"):
                                message_content_to_save = last_message_obj.content
                            
                            if message_content_to_save:
                                role_to_save = "system" # 默认角色为 system 或 agent_step
                                type_to_save = "text"  # 默认类型为 text
                                content_for_db = str(message_content_to_save) # 默认转为字符串

                                # 根据 agent name 决定 role 和 type
                                if name == "reporter":
                                    role_to_save = "assistant"
                                    type_to_save = "text" # reporter 通常输出最终文本报告
                                    # content_for_db 已经是 Markdown 字符串
                                elif name == "planner":
                                    role_to_save = "system" # 或者 "agent_log"
                                    type_to_save = "workflow" # 前端期望的类型
                                    # planner 的 content 通常是计划的 JSON 结构
                                    # 需要确保 message_content_to_save 是前端期望的 workflow 对象结构
                                    # 如果它已经是字典/对象，可以直接 json.dumps
                                    # 如果它是一个包含 JSON 的字符串，可能需要先解析再构造成前端期望的结构
                                    # 假设 planner 的 content 是一个包含 plan 的字典
                                    content_for_db = json.dumps({"workflow": {"type": "plan", "details": message_content_to_save}})
                                elif name == "researcher":
                                    role_to_save = "system"
                                    type_to_save = "workflow" # 前端期望的类型
                                    # researcher 的 content 可能是 Markdown 或结构化数据
                                    # 同样需要构造成前端 WorkflowProgressView 期望的 content.workflow 结构
                                    content_for_db = json.dumps({"workflow": {"type": "research_results", "details": message_content_to_save}})
                                # 只有特定角色的消息才保存，避免重复或无关信息
                                if role_to_save in ["assistant", "system"]: # 或者你定义的其他需要保存的角色
                                    logger.info(f"Saving message from agent {name} with role '{role_to_save}' and type '{type_to_save}'. Content snippet: {content_for_db[:100]}...")
                                    await SessionService.add_message(
                                        db,
                                        session_id,
                                        role_to_save,
                                        content_for_db,
                                        type_to_save
                                    )
                                else:
                                    logger.info(f"Skipping save for message from {name} due to role '{role_to_save}'.")
                            else:
                                logger.info(f"No content extracted from last message of agent {name}.")
                        else:
                            logger.info(f"No messages found in output for agent {name}")
                    except Exception as e:
                        logger.error(f"Error saving assistant message for agent {name}: {e}", exc_info=True)
                    finally:
                        db.close()