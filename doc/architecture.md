# DeepMedical 系统架构文档

## 后端工作流执行逻辑

DeepMedical项目后端采用了基于LangGraph的多智能体协作系统，实现了一个结构化的工作流程。以下从整体架构、工作流初始化、节点交互、数据流转和控制流程等方面详细讲解工作流的执行逻辑。

### 1. 整体架构

DeepMedical的后端工作流基于**有向状态图(StateGraph)**构建，各个智能体作为图中的节点，通过定义的边实现节点间的消息传递和任务流转。

核心组件包括：

- **状态图(StateGraph)**：定义在`build_graph`函数中，是整个工作流的骨架
- **状态对象(State)**：继承自`MessagesState`，包含消息历史和控制参数
- **节点函数**：每个智能体对应一个节点函数，如coordinator_node、planner_node等
- **工作流服务**：run_agent_workflow函数负责工作流的初始化和执行

### 2. 工作流初始化

工作流初始化阶段在`run_agent_workflow`函数中完成：

```python
async def run_agent_workflow(
    user_input_messages: list,
    debug: Optional[bool] = False,
    deep_thinking_mode: Optional[bool] = False,
    search_before_planning: Optional[bool] = False,
    team_members: Optional[list] = None,
):
```

1. **参数处理**：
   - 接收用户消息和配置参数（深度思考模式、搜索前规划等）
   - 初始化工作流ID和团队成员列表

2. **图实例化**：
   - 通过`build_graph()`创建工作流图实例
   - 图结构定义了各个智能体之间的调用关系

3. **状态初始化**：
   - 设置初始状态，包括用户消息、控制参数等
   - 初始化全局变量如缓存和浏览器工具实例

### 3. 节点类型与功能

工作流中的每个节点代表一个专门的智能体，负责特定的任务：

1. **协调员(Coordinator)**：

   ```python
   def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
   ```

   - 作为工作流入口，与用户直接交互
   - 分析用户意图并决定是否将任务交给规划员
   - 决策逻辑：通过检测响应中的`"handoff_to_planner"`标记决定是继续（`goto="planner"`）还是结束（`goto="__end__"`）

2. **规划员(Planner)**：

   ```python
   def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
   ```

   - 生成整体执行计划
   - 如果启用`search_before_planning`，会先使用Tavily API进行网络搜索
   - 根据深度思考模式选择不同的LLM（basic或reasoning）
   - 输出结果需要是有效的JSON格式，否则工作流提前结束

3. **主管(Supervisor)**：

   ```python
   def supervisor_node(state: State) -> Command[Literal[*TEAM_MEMBERS, "__end__"]]:
   ```

   - 负责调度和决策，确定下一步由哪个智能体执行
   - 分析每个智能体的输出并作出下一步决策
   - 当决定任务完成时，路由到"FINISH"（转换为`"__end__"`）

4. **执行者智能体**：
   - **研究员(Researcher)**：收集分析信息
   - **程序员(Coder)**：执行Python代码
   - **浏览器(Browser)**：执行网页浏览和信息检索
   - **汇报员(Reporter)**：生成最终报告

### 4. 工作流执行流程

整体执行流程如下：

1. **初始化阶段**：
   - 用户输入被发送到协调员节点
   - 协调员决定是否启动任务流程

2. **规划阶段**：
   - 如果需要，规划员先进行网络搜索（当`search_before_planning=True`）
   - 规划员生成详细执行计划JSON

3. **执行阶段**：
   - 主管根据规划，将任务分发给各个专门智能体
   - 每个智能体执行完后返回到主管
   - 主管根据当前状态决定下一步行动

4. **完成阶段**：
   - 当主管决定工作流完成时，工作流结束
   - 生成最终状态和响应消息

### 5. 数据流转机制

数据在各节点间的流转通过State对象实现：

```python
class State(MessagesState):
    TEAM_MEMBERS: list[str]
    TEAM_MEMBER_CONFIGRATIONS: dict[str, dict]
    next: str
    full_plan: str
    deep_thinking_mode: bool
    search_before_planning: bool
```

1. **消息传递**：
   - 节点间通过添加新消息传递信息
   - 每个智能体都有唯一的名称标识其消息

2. **状态更新**：
   - 每个节点通过返回`Command`对象更新状态和决定下一个节点
   - 例如：`return Command(update={...}, goto="supervisor")`

3. **控制流**：
   - `goto`字段决定下一个执行的节点
   - 特殊目标`"__end__"`表示工作流结束

### 6. 事件流与前端交互

工作流执行过程中生成多种事件，通过EventSourceResponse流式传输给前端：

1. **事件类型**：
   - `start_of_workflow`：工作流开始
   - `start_of_agent`/`end_of_agent`：智能体开始/结束
   - `message`：智能体生成的消息
   - `tool_call`/`tool_call_result`：工具调用及结果
   - `final_session_state`：最终会话状态

2. **事件生成逻辑**：

   ```python
   async for event in graph.astream_events({...}):
       # 根据event类型和内容生成前端事件
       yield {"event": event_type, "data": {...}}
   ```

### 7. 特殊功能实现

1. **深度思考模式**：

   ```python
   if state.get("deep_thinking_mode"):
       llm = get_llm_by_type("reasoning")
   ```

   - 使用更强大的推理型LLM，进行更深入的分析

2. **联网搜索功能**：

   ```python
   if state.get("search_before_planning"):
       searched_content = tavily_tool.invoke({"query": state["messages"][-1].content})
   ```

   - 在规划前使用Tavily API执行网络搜索
   - 将搜索结果添加到规划员的输入中

3. **错误处理与恢复**：
   - JSON解析错误处理
   - 工作流取消时的资源清理

### 8. 终止条件

工作流在以下情况下终止：

1. 协调员决定不需要进一步处理（没有"handoff_to_planner"）
2. 规划员输出无效JSON
3. 主管决定工作流完成（next="FINISH"）
4. 发生异常或被用户取消

### 9. 工作流程示例

典型工作流执行路径：

1. 用户发送查询 → 协调员分析并转交规划员
2. 规划员（可能先搜索）生成计划 → 主管开始调度
3. 主管根据计划调用研究员、浏览器等智能体
4. 各智能体执行任务并返回结果给主管
5. 主管最终决定工作完成，流程结束

这种基于LangGraph的多智能体工作流架构，使DeepMedical能够灵活地处理复杂的医疗信息查询，各个专门智能体协同工作，共同完成用户的请求。
