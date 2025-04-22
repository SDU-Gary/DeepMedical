# DeepMedical后端开发日志

## 项目背景回顾

DeepMedical项目旨在构建一个基于多智能体协作的医疗信息获取系统。随着项目的推进，后端架构从最初设想的简单微服务模式，演变为基于LangGraph的多智能体协作系统。这种演变主要是考虑到医疗查询的复杂性以及各种智能体协同工作的需求。

## 技术架构选择

在技术选型阶段，经过对比多种框架后，最终选定了以下技术栈：

- **LangGraph**：用于构建多智能体协作的工作流图
- **FastAPI**：作为主要的Web后端框架，提供高性能的API服务
- **SSE (Server-Sent Events)**：实现从服务器到客户端的实时事件流
- **DeepSeek API**：作为底层大语言模型支持

这一技术栈的核心优势在于：

1. LangGraph提供了优雅的方式定义智能体之间的交互关系
2. FastAPI与异步编程模型完美契合，适合处理多智能体并行工作的场景
3. SSE比WebSocket更轻量，适合单向数据流的场景（服务器到客户端）

## 工作流引擎的设计与实现

工作流引擎是整个后端系统的核心，负责协调各个智能体的工作。当前实现采用了有向状态图(StateGraph)模式：

```python
def build_graph():
    """Build and return the agent workflow graph."""
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", research_node)
    builder.add_node("coder", code_node)
    builder.add_node("browser", browser_node)
    builder.add_node("reporter", reporter_node)
    return builder.compile()
```

这种模式允许灵活地定义各个智能体之间的调用关系。例如，所有查询从协调员(coordinator)开始，然后可能转交给规划员(planner)，之后由主管(supervisor)分配给各个专业智能体。

## 智能体节点实现

每个智能体节点都被实现为一个独立的函数，接收当前状态并返回下一步的操作：

### 协调员(Coordinator)

协调员是工作流的入口点，负责初步分析用户查询并决定是否启动完整的工作流程：

```python
def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
    """Coordinator node that communicate with customers."""
    logger.info("Coordinator talking.")
    messages = apply_prompt_template("coordinator", state)
    response = get_llm_by_type(AGENT_LLM_MAP["coordinator"]).invoke(messages)
    
    response_content = response.content
    # 尝试修复可能的JSON输出
    response_content = repair_json_output(response_content)
    
    goto = "__end__"
    if "handoff_to_planner" in response_content:
        goto = "planner"
        
    # 更新response.content为修复后的内容
    response.content = response_content
    
    return Command(goto=goto,)
```

这种设计允许系统快速回答简单问题，同时对复杂问题启动更深入的分析流程。

### 规划员(Planner)

规划员负责为复杂查询生成执行计划，特别注意的是，实现了可选的"网络搜索前置"功能：

```python
def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    """Planner node that generate the full plan."""
    logger.info("Planner generating full plan")
    messages = apply_prompt_template("planner", state)
    
    # 是否启用深度思考模式
    llm = get_llm_by_type("basic")
    if state.get("deep_thinking_mode"):
        llm = get_llm_by_type("reasoning")
    
    # 联网搜索功能
    if state.get("search_before_planning"):
        searched_content = tavily_tool.invoke({"query": state["messages"][-1].content})
        if isinstance(searched_content, list):
            messages = deepcopy(messages)
            messages[-1].content += f"\n\n# 相关搜索结果\n\n{json.dumps([{'title': elem['title'], 'content': elem['content']} for elem in searched_content], ensure_ascii=False)}"
        else:
            logger.error(f"Tavily搜索返回格式错误: {searched_content}")
    
    # 生成并处理规划响应
    stream = llm.stream(messages)
    full_response = ""
    for chunk in stream:
        full_response += chunk.content
        
    # 处理JSON格式与错误...
    
    return Command(
        update={
            "messages": [HumanMessage(content=full_response, name="planner")],
            "full_plan": full_response,
        },
        goto=goto,
    )
```

联网搜索功能虽然简单，但对于医疗查询特别有价值，因为它允许系统获取最新的医学信息，提高回答的准确性和时效性。

### 主管(Supervisor)

主管节点是整个系统的调度中心，负责根据执行计划分配任务给各个专业智能体：

```python
def supervisor_node(state: State) -> Command[Literal[*TEAM_MEMBERS, "__end__"]]:
    """Supervisor node that decides which agent should act next."""
    logger.info("Supervisor evaluating next action")
    messages = apply_prompt_template("supervisor", state)
    
    # 预处理消息使主管执行更好
    messages = deepcopy(messages)
    for message in messages:
        if isinstance(message, BaseMessage) and message.name in TEAM_MEMBERS:
            message.content = RESPONSE_FORMAT.format(message.name, message.content)
    
    response = (
        get_llm_by_type(AGENT_LLM_MAP["supervisor"])
        .with_structured_output(schema=Router, method="json_mode")
        .invoke(messages)
    )
    goto = response["next"]
    
    if goto == "FINISH":
        goto = "__end__"
        logger.info("Workflow completed")
    else:
        logger.info(f"Supervisor delegating to: {goto}")
        
    return Command(goto=goto, update={"next": goto})
```

值得注意的是，主管使用了结构化输出(structured_output)，这确保了返回结果是符合预期的格式，提高了系统的健壮性。

## 事件流与前端通信

为实现流式响应，开发了基于SSE的事件流机制，允许后端实时向前端推送各种事件：

```python
async def run_agent_workflow(
    user_input_messages: list,
    debug: Optional[bool] = False,
    deep_thinking_mode: Optional[bool] = False,
    search_before_planning: Optional[bool] = False,
    team_members: Optional[list] = None,
):
    """运行代理工作流来处理并响应用户输入消息。"""
    # 参数验证和初始化...
    
    async for event in graph.astream_events({
        # 各种初始状态参数...
    }, version="v2"):
        # 事件处理和分类
        kind = event.get("event")
        data = event.get("data")
        name = event.get("name")
        # ...
        
        # 根据事件类型生成前端事件
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
            # 其他事件类型处理...
```

这种事件流机制是实现前端工作流可视化的关键。通过细粒度的事件，前端可以实时展示每个智能体的工作状态、思考过程和工具使用情况。

## 工具集成与扩展

为赋予智能体更强的能力，集成了多种外部工具：

### Tavily搜索工具

集成Tavily API进行网络搜索，特别适用于获取最新医疗信息：

```python
# tavily_tool实现示例
from langchain.tools import TavilySearchAPIWrapper

search = TavilySearchAPIWrapper()
tavily_tool = Tool(
    name="tavily_search",
    description="Search the web for information using Tavily API",
    func=lambda query: search.results(query),
)
```

### 浏览器工具

特别开发了browser_tool，允许智能体进行网页浏览和信息提取：

```python
class browser_tool:
    """Browser tool for web browsing and information extraction."""
    
    @staticmethod
    async def browse(url: str):
        """Browse a webpage and extract its content."""
        async with browser_manager.get_browser() as browser:
            page = await browser.new_page()
            await page.goto(url)
            content = await page.content()
            text = extract_text_from_html(content)
            return text
    
    @staticmethod
    async def screenshot(url: str, output_path: str):
        """Take a screenshot of a webpage."""
        # 实现细节...
    
    @staticmethod
    async def terminate():
        """Terminate all browser instances."""
        await browser_manager.close_all()
```

## 主要挑战与解决方案

### 挑战1: 智能体协调与状态管理

在多个智能体协同工作时，状态管理变得极为复杂。特别是当一个智能体的输出需要作为另一个智能体的输入时。

**解决方案**: 采用MessagesState作为基础状态类型，并扩展了State类来包含工作流所需的其他字段：

```python
class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""
    
    # 常量
    TEAM_MEMBERS: list[str]
    TEAM_MEMBER_CONFIGRATIONS: dict[str, dict]
    
    # 运行时变量
    next: str
    full_plan: str
    deep_thinking_mode: bool
    search_before_planning: bool
```

### 挑战2: 事件流中的错误处理

在长时间运行的事件流中，错误处理变得尤为重要，特别是当用户取消请求时，需要确保所有资源都被正确释放。

**解决方案**: 实现了全面的错误处理和资源清理机制：

```python
try:
    async for event in graph.astream_events(...):
        # 事件处理...
except asyncio.CancelledError:
    logger.info("Workflow cancelled, terminating browser agent if exists")
    if current_browser_tool:
        await current_browser_tool.terminate()
    raise
except Exception as e:
    logger.error(f"Error in workflow: {e}")
    # 错误处理...
finally:
    # 资源清理...
```

### 挑战3: LLM输出解析与修复

LLM输出有时不符合预期格式，特别是在生成JSON时容易出现格式错误。

**解决方案**: 实现了专门的JSON修复函数：

```python
def repair_json_output(content: str) -> str:
    """尝试修复可能的JSON输出格式问题。"""
    # JSON片段检测逻辑
    json_start = content.find("```json")
    if json_start != -1:
        json_end = content.find("```", json_start + 6)
        if json_end != -1:
            json_text = content[json_start + 7:json_end].strip()
            try:
                parsed = json.loads(json_text)
                return json.dumps(parsed, ensure_ascii=False)  
            except json.JSONDecodeError:
                try:
                    # 尝试修复常见JSON错误
                    repaired = json_repair.loads(json_text)
                    return json.dumps(repaired, ensure_ascii=False)
                except:
                    pass
    return content
```

这种修复机制大大提高了系统的健壮性，使其能够处理LLM返回的不完美输出。

## 优化与性能考量

医疗信息查询往往涉及大量文本处理和复杂推理，性能优化至关重要：

### 异步并行处理

大量使用了异步编程，允许多个操作并行执行：

```python
async def perform_research(topics: List[str]):
    """Perform research on multiple topics in parallel."""
    research_tasks = [research_single_topic(topic) for topic in topics]
    results = await asyncio.gather(*research_tasks)
    return results
```

### 智能缓存

实现了针对协调员响应的缓存机制，避免冗余处理：

```python
# 协调员缓存机制
coordinator_cache = []
if node == "coordinator":
    if len(coordinator_cache) < MAX_CACHE_SIZE:
        coordinator_cache.append(content)
        cached_content = "".join(coordinator_cache)
        # 缓存处理逻辑...
```

## 下一步开发计划

目前后端系统已经实现了基本的工作流功能，但仍有多个方向需要进一步开发：

1. **改进反爬措施**：增强网络数据采集的稳定性和成功率
2. **中文响应优化**：确保系统始终以中文响应用户查询
3. **会话持久化**：实现会话状态的持久存储，支持页面刷新后继续对话
4. **智能体能力扩展**：为各个智能体增加更专业的医疗领域能力

接下来的工作将优先集中在这些方向上，特别是中文响应优化和会话持久化功能，因为这两项对用户体验影响较大。
