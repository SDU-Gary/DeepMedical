import logging
from typing import Optional
import asyncio

from src.config import TEAM_MEMBER_CONFIGRATIONS, TEAM_MEMBERS
from src.graph import build_graph
from src.tools.browser import browser_tool
from langchain_community.adapters.openai import convert_message_to_dict
import uuid
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default level is INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def enable_debug_logging():
    """Enable debug level logging for more detailed execution information."""
    logging.getLogger("src").setLevel(logging.DEBUG)


logger = logging.getLogger(__name__)

# Create the graph
graph = build_graph()

# Cache for coordinator messages
MAX_CACHE_SIZE = 3

# Global variable to track current browser tool instance
current_browser_tool: Optional[browser_tool] = None


async def run_agent_workflow(
    user_input_messages: list,
    debug: Optional[bool] = False,
    deep_thinking_mode: Optional[bool] = False,
    search_before_planning: Optional[bool] = False,
    team_members: Optional[list] = None,
    session_id: Optional[str] = None,  # 新增参数
):
    import uuid
    """Run the agent workflow to process and respond to user input messages.

    This function orchestrates the execution of various agents in a workflow to handle
    user requests. It manages agent communication, tool usage, and generates streaming
    events for the workflow progress.

    Args:
        user_input_messages: List of user messages to process in the workflow
        debug: If True, enables debug level logging for detailed execution information
        deep_thinking_mode: If True, enables more thorough analysis and consideration
            in agent responses
        search_before_planning: If True, performs preliminary research before creating
            the execution plan
        team_members: Optional list of specific team members to involve in the workflow.
            If None, uses default TEAM_MEMBERS configuration

    Returns:
        Yields various event dictionaries containing workflow state and progress information,
        including agent activities, tool calls, and the final workflow state

    Raises:
        ValueError: If user_input_messages is empty
        asyncio.CancelledError: If the workflow is cancelled during execution
    """
    if not user_input_messages:
        raise ValueError("Input could not be empty")

    if debug:
        enable_debug_logging()

    logger.info(f"Starting workflow with user input: {user_input_messages}")
    
    # 如果没有提供session_id，创建新会话
    if not session_id:
        from src.database.db import SessionLocal
        from src.service.session_service import SessionService
        
        db = SessionLocal()
        try:
            session = await SessionService.create_session(db)
            session_id = session.id
            logger.info(f"Created new session: {session_id}")
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            # 即使创建会话失败，也继续执行工作流
        finally:
            db.close()
    else:
        logger.info(f"Using existing session: {session_id}")

    workflow_id = str(uuid.uuid4())

    team_members = team_members if team_members else TEAM_MEMBERS

    streaming_llm_agents = [*team_members, "planner", "coordinator"]

    # Reset coordinator cache at the start of each workflow
    global current_browser_tool
    coordinator_cache = []
    current_browser_tool = browser_tool
    is_handoff_case = False
    is_workflow_triggered = False

    # 注意：用户输入消息应该已经在 /api/chat/initiate 端点存储
    # 这里不再重复保存用户消息，避免重复存储问题
    logger.info(f"Using existing session ID {session_id}, skipping user message storage to avoid duplicates")
    
    try:
        async for event in graph.astream_events(
            {
                # Constants
                "TEAM_MEMBERS": team_members,
                "TEAM_MEMBER_CONFIGRATIONS": TEAM_MEMBER_CONFIGRATIONS,
                # Runtime Variables
                "messages": user_input_messages,
                "deep_thinking_mode": deep_thinking_mode,
                "search_before_planning": search_before_planning,
                "session_id": session_id,  # 传递session_id
            },
            version="v2",
        ):
            kind = event.get("event")
            data = event.get("data")
            name = event.get("name")
            metadata = event.get("metadata")
            node = (
                ""
                if (metadata.get("checkpoint_ns") is None)
                else metadata.get("checkpoint_ns").split(":")[0]
            )
            langgraph_step = (
                ""
                if (metadata.get("langgraph_step") is None)
                else str(metadata["langgraph_step"])
            )
            run_id = "" if (event.get("run_id") is None) else str(event["run_id"])

            if kind == "on_chain_start" and name in streaming_llm_agents:
                if name == "planner":
                    is_workflow_triggered = True
                    yield {
                        "event": "start_of_workflow",
                        "data": {
                            "workflow_id": workflow_id,
                            "input": user_input_messages,
                        },
                    }
                ydata = {
                    "event": "start_of_agent",
                    "data": {
                        "agent_name": name,
                        "agent_id": f"{workflow_id}_{name}_{langgraph_step}",
                    },
                }
            # workflow_service.py中的on_chain_end事件处理逻辑
            elif kind == "on_chain_end" and name in streaming_llm_agents:
                # 如果有session_id，保存消息到数据库
                if session_id:
                    from src.database.db import SessionLocal
                    from src.service.session_service import SessionService
                    from langchain_core.messages import AIMessage, HumanMessage
                    import uuid
                    
                    db = SessionLocal()
                    logger.info(f"ON_CHAIN_END for agent: {name}. Processing output for saving.")
                    try:
                        output_data = data.get("output")
                        messages_to_save = []

                        # 正确提取消息列表
                        if isinstance(output_data, dict) and output_data.get("messages"):
                            messages_to_save = output_data["messages"]
                        elif hasattr(output_data, "update") and isinstance(output_data.update, dict) and output_data.update.get("messages"):
                            # 如果是Command对象
                            messages_to_save = output_data.update["messages"]

                        if messages_to_save and len(messages_to_save) > 0:
                            last_message_obj = messages_to_save[-1]  # LangChain消息对象
                            logger.info(f"Last message object from {name}'s output: {last_message_obj}")

                            raw_content_from_agent = None
                            if hasattr(last_message_obj, "content"):
                                raw_content_from_agent = last_message_obj.content
                            
                            if raw_content_from_agent:
                                role_to_save = "system"  # 默认为系统消息
                                type_to_save = "text"    # 默认为文本类型
                                content_for_db = str(raw_content_from_agent)
                                should_save = False      # 是否保存的标志
                                
                                # 根据不同的agent类型处理消息
                                if name == "reporter":
                                    # reporter生成最终报告，保存为assistant的文本消息
                                    role_to_save = "assistant"
                                    type_to_save = "text"
                                    content_for_db = str(raw_content_from_agent)
                                    should_save = True
                                
                                elif name == "planner":
                                    # planner输出计划，保存为workflow类型
                                    role_to_save = "system"  # 或assistant，取决于UI展示需求
                                    type_to_save = "workflow"
                                    
                                    # 尝试解析planner输出
                                    try:
                                        # 假设raw_content_from_agent可能是JSON字符串或已经是对象
                                        if isinstance(raw_content_from_agent, str):
                                            try:
                                                plan_details = json.loads(raw_content_from_agent)
                                            except json.JSONDecodeError:
                                                plan_details = {"content": raw_content_from_agent}
                                        else:
                                            plan_details = raw_content_from_agent
                                        
                                        # 构造前端期望的workflow结构
                                        workflow_id = f"workflow-planner-{str(uuid.uuid4())[:8]}"
                                        step_id = f"step-planner-{str(uuid.uuid4())[:8]}"
                                        task_id = f"task-planner-{str(uuid.uuid4())[:8]}"
                                        
                                        workflow_data = {
                                            "workflow": {
                                                "id": workflow_id,
                                                "name": "执行计划",
                                                "steps": [
                                                    {
                                                        "id": step_id,
                                                        "type": "agentic",
                                                        "agentId": f"{name}-{workflow_id}",
                                                        "agentName": name,
                                                        "tasks": [
                                                            {
                                                                "id": task_id,
                                                                "type": "thinking",
                                                                "state": "success",
                                                                "payload": {
                                                                    "text": json.dumps(plan_details, ensure_ascii=False, indent=2),
                                                                    "reason": "计划已生成"
                                                                }
                                                            }
                                                        ],
                                                        "isCompleted": True
                                                    }
                                                ],
                                                "isCompleted": False
                                            }
                                        }
                                        
                                        content_for_db = json.dumps(workflow_data, ensure_ascii=False)
                                        should_save = True
                                    
                                    except Exception as e:
                                        logger.error(f"Error constructing workflow message for planner: {e}")
                                        # 即使出错也保存一些内容，方便调试
                                        content_for_db = json.dumps({
                                            "workflow": {
                                                "id": f"error-{str(uuid.uuid4())[:8]}",
                                                "name": "处理计划时出错",
                                                "steps": [
                                                    {
                                                        "id": f"error-step-{str(uuid.uuid4())[:8]}",
                                                        "type": "agentic",
                                                        "agentId": f"error-{name}",
                                                        "agentName": name,
                                                        "tasks": [
                                                            {
                                                                "id": f"error-task-{str(uuid.uuid4())[:8]}",
                                                                "type": "thinking",
                                                                "state": "error",
                                                                "payload": {
                                                                    "text": f"处理计划数据时出错: {str(e)}\n原始内容:\n{raw_content_from_agent[:500]}"
                                                                }
                                                            }
                                                        ],
                                                        "isCompleted": True
                                                    }
                                                ],
                                                "isCompleted": True
                                            }
                                        }, ensure_ascii=False)
                                        should_save = True
                                
                                elif name == "researcher":
                                    # researcher输出研究结果，保存为workflow类型
                                    role_to_save = "system"
                                    type_to_save = "workflow"
                                    
                                    # 构造researcher的workflow结构
                                    workflow_id = f"workflow-researcher-{str(uuid.uuid4())[:8]}"
                                    
                                    workflow_data = {
                                        "workflow": {
                                            "id": workflow_id,
                                            "name": "研究发现",
                                            "steps": [
                                                {
                                                    "id": f"step-researcher-{str(uuid.uuid4())[:8]}",
                                                    "type": "agentic",
                                                    "agentId": f"{name}-{workflow_id}",
                                                    "agentName": name,
                                                    "tasks": [
                                                        {
                                                            "id": f"task-researcher-{str(uuid.uuid4())[:8]}",
                                                            "type": "thinking",
                                                            "state": "success",
                                                            "payload": {
                                                                "text": str(raw_content_from_agent)
                                                            }
                                                        }
                                                    ],
                                                    "isCompleted": True
                                                }
                                            ],
                                            "isCompleted": False
                                        }
                                    }
                                    
                                    content_for_db = json.dumps(workflow_data, ensure_ascii=False)
                                    should_save = True
                                
                                # 这里可以添加其他agent类型的处理逻辑
                                
                                # 如果确定要保存，则调用保存函数
                                if should_save:
                                    logger.info(f"Saving message from agent {name} with role '{role_to_save}' and type '{type_to_save}'")
                                    await SessionService.add_message(
                                        db,
                                        session_id,
                                        role_to_save,
                                        content_for_db,
                                        type_to_save
                                    )
                                else:
                                    logger.info(f"Skipping save for message from {name} (not meeting save criteria)")
                            else:
                                logger.info(f"No content extracted from last message of agent {name}")
                        else:
                            logger.info(f"No messages found in output for agent {name}")
                    except Exception as e:
                        logger.error(f"Error processing or saving message for agent {name}: {e}", exc_info=True)
                    finally:
                        db.close()
                
                ydata = {
                    "event": "end_of_agent",
                    "data": {
                        "agent_name": name,
                        "agent_id": f"{workflow_id}_{name}_{langgraph_step}",
                    },
                }
            elif kind == "on_chat_model_start" and node in streaming_llm_agents:
                ydata = {
                    "event": "start_of_llm",
                    "data": {"agent_name": node},
                }
            elif kind == "on_chat_model_end" and node in streaming_llm_agents:
                ydata = {
                    "event": "end_of_llm",
                    "data": {"agent_name": node},
                }
            elif kind == "on_chat_model_stream" and node in streaming_llm_agents:
                content = data["chunk"].content
                if content is None or content == "":
                    if not data["chunk"].additional_kwargs.get("reasoning_content"):
                        # Skip empty messages
                        continue
                    ydata = {
                        "event": "message",
                        "data": {
                            "message_id": data["chunk"].id,
                            "delta": {
                                "reasoning_content": (
                                    data["chunk"].additional_kwargs["reasoning_content"]
                                )
                            },
                        },
                    }
                else:
                    # Check if the message is from the coordinator
                    if node == "coordinator":
                        if len(coordinator_cache) < MAX_CACHE_SIZE:
                            coordinator_cache.append(content)
                            cached_content = "".join(coordinator_cache)
                            if cached_content.startswith("handoff"):
                                is_handoff_case = True
                                continue
                            if len(coordinator_cache) < MAX_CACHE_SIZE:
                                continue
                            # Send the cached message
                            ydata = {
                                "event": "message",
                                "data": {
                                    "message_id": data["chunk"].id,
                                    "delta": {"content": cached_content},
                                },
                            }
                        elif not is_handoff_case:
                            # For other agents, send the message directly
                            ydata = {
                                "event": "message",
                                "data": {
                                    "message_id": data["chunk"].id,
                                    "delta": {"content": content},
                                },
                            }
                    else:
                        # For other agents, send the message directly
                        ydata = {
                            "event": "message",
                            "data": {
                                "message_id": data["chunk"].id,
                                "delta": {"content": content},
                            },
                        }
            elif kind == "on_tool_start" and node in team_members:
                ydata = {
                    "event": "tool_call",
                    "data": {
                        "tool_call_id": f"{workflow_id}_{node}_{name}_{run_id}",
                        "tool_name": name,
                        "tool_input": data.get("input"),
                    },
                }
            elif kind == "on_tool_end" and node in team_members:
                ydata = {
                    "event": "tool_call_result",
                    "data": {
                        "tool_call_id": f"{workflow_id}_{node}_{name}_{run_id}",
                        "tool_name": name,
                        "tool_result": (
                            data["output"].content if data.get("output") else ""
                        ),
                    },
                }
            elif kind == "final_session_state":
                # 如果有session_id，保存最终状态到数据库
                if session_id:
                    from src.database.db import SessionLocal
                    from src.service.session_service import SessionService
                    
                    db = SessionLocal()
                    try:
                        await SessionService.update_session_state(db, session_id, data)
                    except Exception as e:
                        logger.error(f"Error updating session state: {e}")
                    finally:
                        db.close()
                
                ydata = {
                    "event": "final_session_state",
                    "data": data,
                }
            else:
                continue
            yield ydata
    except asyncio.CancelledError:
        logger.info("Workflow cancelled, terminating browser agent if exists")
        if current_browser_tool:
            await current_browser_tool.terminate()
        raise

    if is_workflow_triggered:
        # TODO: remove messages attributes after Frontend being compatible with final_session_state event.
        yield {
            "event": "end_of_workflow",
            "data": {
                "workflow_id": workflow_id,
                "messages": [
                    convert_message_to_dict(msg)
                    for msg in data["output"].get("messages", [])
                ],
            },
        }
    # 准备最终状态数据
    final_state = {
        "messages": [
            convert_message_to_dict(msg)
            for msg in data["output"].get("messages", [])
        ],
    }
    
    # 将最终状态发送给前端
    yield {
        "event": "final_session_state",
        "data": final_state,
    }
    
    # 保存最终助手回复到数据库
    if session_id and final_state.get("messages") and len(final_state["messages"]) > 0:
        try:
            from src.database.db import SessionLocal
            from src.service.session_service import SessionService
            
            db = SessionLocal()
            try:
                # 获取最后一条消息（通常是助手的回复）
                final_message = final_state["messages"][-1]
                
                # 确保这是助手消息
                if final_message.get("type") == "AIMessage" or final_message.get("role") == "assistant":
                    # 提取消息内容
                    message_content = None
                    if isinstance(final_message.get("content"), str):
                        message_content = final_message["content"]
                    elif isinstance(final_message.get("content"), dict) and "text" in final_message.get("content", {}):
                        message_content = final_message["content"]["text"]
                    
                    if message_content:
                        logger.info(f"Saving final assistant message to session {session_id}")
                        await SessionService.add_message(
                            db,
                            session_id,
                            "assistant",
                            message_content,  # 内容
                            "text"  # 类型
                        )
            except Exception as e:
                logger.error(f"Error saving final assistant message: {e}", exc_info=True)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in database connection when saving final message: {e}", exc_info=True)
    
    # 将最终状态保存到数据库
    if session_id:
        try:
            # 获取数据库连接
            from src.database.db import get_db
            db = next(get_db())
            
            # 准备可序列化的状态数据
            serializable_state = {}
            if isinstance(data["output"], dict):
                # 复制基本字段
                for key, value in data["output"].items():
                    if key == "messages":
                        # 特殊处理消息列表，确保每个消息都是可序列化的字典
                        serializable_state["messages"] = []
                        for msg in data["output"].get("messages", []):
                            if hasattr(msg, "content") and hasattr(msg, "additional_kwargs"):
                                # 这是一个消息对象，需要转换
                                msg_dict = {
                                    "content": msg.content,
                                    "type": msg.__class__.__name__,
                                    "additional_kwargs": msg.additional_kwargs
                                }
                                if hasattr(msg, "id") and msg.id:
                                    msg_dict["id"] = msg.id
                                serializable_state["messages"].append(msg_dict)
                            elif isinstance(msg, dict):
                                # 已经是字典，但可能包含非序列化对象
                                serializable_msg = {}
                                for msg_key, msg_value in msg.items():
                                    # 简单处理，跳过不可序列化的值
                                    try:
                                        json.dumps({msg_key: msg_value})
                                        serializable_msg[msg_key] = msg_value
                                    except (TypeError, OverflowError):
                                        # 不可序列化，转为字符串
                                        serializable_msg[msg_key] = str(msg_value)
                                serializable_state["messages"].append(serializable_msg)
                            else:
                                # 其他情况，转为字符串
                                serializable_state["messages"].append({"content": str(msg)})
                    else:
                        # 其他字段，尝试序列化，失败则转为字符串
                        try:
                            json.dumps({key: value})
                            serializable_state[key] = value
                        except (TypeError, OverflowError):
                            serializable_state[key] = str(value)
            
            # 保存最终状态
            from src.service.session_service import SessionService
            await SessionService.update_session_state(
                db=db, 
                session_id=session_id, 
                state=serializable_state  # 确保可序列化的状态
            )
            logger.info(f"Final state saved to session {session_id}")
        except Exception as e:
            logger.error(f"Error saving final state to session {session_id}: {e}", exc_info=True)
        finally:
            db.close()
    
    # 使用yield返回session_id给调用者（而不是return）
    yield {
        "type": "session_id",
        "data": {
            "session_id": session_id
        }
    }
