# DeepMedical前端开发日志：多智能体工作流可视化之旅

## 项目进展

### 初期技术选型

在技术选型阶段，我权衡了多种前端框架，最终选择了Next.js(App Router) + React + TypeScript的组合：

- **Next.js**：提供了强大的路由、SSR以及优秀的开发体验
- **React**：组件化开发体验和丰富的生态系统
- **TypeScript**：提供类型安全，特别是在处理复杂的后端API响应时

状态管理方面，我选择了Zustand而非Redux，主要考虑因素是：

1. 更轻量级的API，减少样板代码
2. 更灵活的状态组织方式
3. 与React hooks的无缝集成

```typescript
// 核心状态定义
export const useStore = create<{
  teamMembers: TeamMember[];
  enabledTeamMembers: string[];
  messages: Message[];
  responding: boolean;
  state: { messages: { role: string; content: string }[] };
}>(() => ({
  teamMembers: [],
  enabledTeamMembers: [],
  messages: [],
  responding: false,
  state: { messages: [] },
}));
```

## 核心挑战：实时工作流可视化

开发过程中最大的挑战是如何直观地展示后端复杂的多智能体工作流。与普通聊天机器人不同，DeepMedical的后端由多个专门智能体协作完成任务，包括协调员、规划员、研究员等角色，每个智能体都有其独特的职责。

### 第一次尝试：扁平化消息列表

最初，我尝试将所有智能体的活动以普通消息的形式展示在对话历史中：

```tsx
// 初版消息视图 (简化版)
function MessageView({ message }) {
  if (message.agentName) {
    return <div className="agent-message">{message.content}</div>;
  }
  return <div className="user-message">{message.content}</div>;
}
```

但很快我发现这种方式存在问题：

1. 用户被大量智能体交互信息淹没
2. 无法直观地理解工作流程
3. 技术细节过多，影响用户体验

### 改进：工作流组件的设计与实现

经过团队讨论，我决定设计专门的工作流可视化组件。这个组件需要将复杂的工作流程以直观、友好的方式呈现给用户。

首先，我设计了工作流数据模型：

```typescript
// 工作流步骤类型
type WorkflowStep = {
  id: string;
  agentId: string;
  agentName: string;
  type: "agentic";
  isCompleted: boolean;
  tasks: (ThinkingTask | ToolCallTask)[];
};

// 工作流定义
type Workflow = {
  id: string;
  name: string;
  steps: WorkflowStep[];
  finalState?: any;
  isCompleted?: boolean;
};
```

接着，我实现了`WorkflowEngine`类来解析和处理后端发送的事件流：

```typescript
export class WorkflowEngine {
  start(startEvent: StartOfWorkflowEvent) {
    const workflow: Workflow = {
      id: startEvent.data.workflow_id,
      name: startEvent.data.input[0]!.content,
      steps: [],
    };
    this._workflow = workflow;
    return workflow;
  }
  
  async *run(stream: AsyncIterable<ChatEvent>) {
    // 处理工作流事件...
  }
}
```

这个引擎负责将后端发送的各种事件（智能体启动、思考过程、工具调用等）转换为前端可视化所需的数据结构。

## 实时数据流与服务器发送事件(SSE)

另一个技术挑战是如何处理实时数据流。传统的HTTP请求-响应模式无法满足需求，我需要一种能够接收持续更新的机制。

最初我考虑了WebSocket，但考虑到数据流主要是单向的（服务器到客户端），我最终选择了更轻量的SSE(Server-Sent Events)技术：

```typescript
// 简化的SSE客户端实现
export async function* fetchStream<T>(url: string, options: RequestInit = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Response body is null");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";
      
      for (const line of lines) {
        if (line.trim() === "") continue;
        if (line.startsWith("data:")) {
          const data = line.slice(5).trim();
          try {
            yield JSON.parse(data) as T;
          } catch (e) {
            console.error("Failed to parse SSE data:", data);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

这种实现允许我以异步迭代器的形式处理事件流，非常适合与React的状态更新机制集成。

## 用户体验考量：交互设计与反馈机制

除了功能实现，我非常注重用户体验的设计。医疗信息查询是一个严肃的领域，用户界面必须既专业又友好。

### 状态反馈与等待时间

医疗查询可能需要一定的处理时间，尤其是涉及网络搜索和复杂分析时。我设计了多层次的状态反馈机制：

1. **全局响应指示器**：顶部进度条显示查询处理状态
2. **打字动画**：模拟实时打字效果，让等待过程更自然
3. **可取消机制**：允许用户随时取消长时间运行的查询

```tsx
// 发送按钮状态切换
<Button
  variant="outline"
  size="icon"
  className={cn(
    "h-10 w-10 rounded-full transition-colors duration-200",
    responding
      ? "bg-destructive/90 text-white hover:bg-destructive"
      : "bg-primary text-white hover:bg-primary/80",
  )}
  onClick={handleSendMessage}
>
  {responding ? (
    <div className="flex h-10 w-10 items-center justify-center">
      <div className="h-4 w-4 rounded-sm bg-white/80" />
    </div>
  ) : (
    <ArrowUpOutlined className="text-white" />
  )}
</Button>
```

### 控制与配置

我添加了几个关键控制选项，让用户能够根据需求调整系统行为：

1. **深度思考模式**：启用更全面但可能更慢的分析
2. **联网搜索**：控制是否在规划前进行网络搜索
3. **团队成员配置**：自定义启用的智能体组合

这些选项被设计为简单的开关按钮，配有清晰的视觉指示和工具提示说明。

## 遇到的问题与解决方案

### 问题1：WorkflowProgressView性能问题

随着工作流复杂度增加，`WorkflowProgressView`组件开始出现性能问题，特别是在工作流包含大量步骤和任务时。

**解决方案**：我引入了虚拟化列表和懒加载机制，只渲染用户当前可见的部分，并实现了展开/折叠功能，让用户可以控制显示的细节级别。

```tsx
// 展开/折叠控制
const [isExpanded, setIsExpanded] = useState(false);
useEffect(() => {
  if (isExpanded) {
    setBlockWidth(1200);
    setBlockHeight(window.innerHeight - 320);
    // ...
  } else {
    setBlockWidth(928);
    setBlockHeight(400);
  }
}, [isExpanded]);
```

### 问题2：实时更新与滚动位置

在接收实时更新时，页面滚动位置会频繁变化，导致糟糕的用户体验。

**解决方案**：实现了智能滚动逻辑，只在特定情况下自动滚动，并添加了平滑滚动效果：

```tsx
// 自定义hook: useAutoScrollToBottom
export function useAutoScrollToBottom(
  ref: React.RefObject<HTMLElement>,
  shouldScroll: boolean,
) {
  useEffect(() => {
    if (shouldScroll && ref.current) {
      const element = ref.current;
      // 计算是否已接近底部
      const isNearBottom =
        element.scrollHeight - element.scrollTop - element.clientHeight < 100;
      
      if (isNearBottom) {
        element.scrollTo({
          top: element.scrollHeight,
          behavior: "smooth",
        });
      }
    }
  }, [ref, shouldScroll]);
}
```

## 未来工作规划

虽然当前版本已经实现了核心功能，但仍有许多优化和扩展计划：

1. **本地存储增强**：实现完整的会话管理，包括导出和导入功能
2. **多语言支持**：增强国际化支持，确保所有界面和响应都能以用户首选语言呈现
3. **医疗数据可视化增强**：集成专业的医疗数据可视化组件，如解剖图、统计图表等
