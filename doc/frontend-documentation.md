# DeepMedical 前端架构与实现

## 目录

1. [前端架构概述](#前端架构概述)
2. [用户界面设计](#用户界面设计)
3. [关键组件解析](#关键组件解析)
4. [多智能体工作流可视化](#多智能体工作流可视化)
5. [状态管理与数据流](#状态管理与数据流)
6. [功能特色与用户体验](#功能特色与用户体验)
7. [技术实现细节](#技术实现细节)
8. [未来优化方向](#未来优化方向)

## 前端架构概述

DeepMedical前端采用现代化的React技术栈，基于Next.js框架构建，实现了一个流畅、响应式的医疗数据查询界面。系统架构清晰简洁，主要由以下几个部分组成：

- **核心页面结构**：基于Next.js的App Router模式构建
- **组件系统**：功能化、模块化的UI组件
- **状态管理**：基于Zustand的轻量级状态管理
- **API通信**：服务器发送事件(SSE)与后端实时通信
- **工作流可视化**：多智能体协作的直观展示

前端设计遵循现代医疗应用的设计准则，确保用户在查询医疗信息时获得专业、可靠且易于理解的体验。整体架构实现了前端与后端的松耦合，通过类型化的API接口进行通信，保证了系统的可维护性和可扩展性。

## 用户界面设计

DeepMedical的用户界面采用简洁明了的设计风格，专注于提供高效的医疗信息查询体验。

### 界面布局

主界面采用垂直流式布局，主要包含以下几个部分：

1. **顶部导航栏**：提供应用标识和基础导航功能
2. **对话历史区域**：展示用户查询和系统回复的历史记录
3. **多智能体工作流可视化**：直观展示后端智能体的工作过程
4. **输入控制区**：用户输入查询并控制高级功能的区域

![image-20250413191716018](https://kyrie-figurebed.oss-cn-beijing.aliyuncs.com/img/image-20250413191716018.png)

### 响应式设计

界面适配不同设备屏幕尺寸，为用户提供一致的体验：

- **大屏设备**：全功能视图，工作流可视化完全展开
- **平板设备**：优化布局以保证核心功能可用性
- **移动设备**：专注于查询和结果展示，简化工作流视图

## 关键组件解析

### 输入控制组件 (InputBox)

InputBox组件是用户与系统交互的主要入口，负责接收用户输入并提供高级功能控制。

```tsx
const [deepThinkingMode, setDeepThinkMode] = useState(false);
const [searchBeforePlanning, setSearchBeforePlanning] = useState(false);
```

该组件提供以下核心功能：

- **文本输入区**：用户输入医疗查询的主要区域
- **深度思考模式**：启用更深入的分析思考
- **联网搜索选项**：控制是否在规划前进行在线搜索
- **团队成员配置**：可以自定义启用的智能体组合

![image-20250413191747985](https://kyrie-figurebed.oss-cn-beijing.aliyuncs.com/img/image-20250413191747985.png)

### 消息历史视图 (MessageHistoryView)

展示用户与系统的对话历史，支持富文本格式和多种消息类型：

```tsx
function MessageView({ message }: { message: Message }) {
  if (message.type === "text" && message.content) {
    // 渲染文本消息...
  } else if (message.type === "workflow") {
    // 渲染工作流可视化...
  }
  return null;
}
```

特点包括：

- **差异化消息样式**：用户和系统消息采用不同的视觉风格
- **Markdown渲染**：支持富文本格式，便于展示结构化医疗信息
- **自动滚动**：新消息出现时自动滚动到底部

### 工作流进度视图 (WorkflowProgressView)

系统最具特色的组件之一，直观展示多智能体协作过程：

```tsx
export function WorkflowProgressView({
  className,
  workflow,
}: {
  className?: string;
  workflow: Workflow;
}) {
  // 组件实现...
}
```

该组件提供以下功能：

- **智能体执行进度**：实时展示各个智能体的工作状态
- **思考过程可视化**：展示"深度思考"过程中的推理步骤
- **工具调用视图**：显示智能体使用工具的详细过程
- **可展开/折叠**：允许用户查看更多或更少的执行细节

## 多智能体工作流可视化

工作流可视化是DeepMedical前端的核心特色，让用户能够直观地了解系统如何处理他们的医疗查询。

### 工作流引擎

前端通过WorkflowEngine类管理和解析后端发送的工作流事件：

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
    // 处理工作流事件流...
  }
}
```

### 工作流步骤类型

系统支持多种工作流步骤类型：

1. **智能体步骤**：展示不同角色（规划员、研究员等）的工作过程
2. **思考任务**：显示LLM的思考过程和推理路径
3. **工具调用任务**：展示各种工具（如搜索、浏览器）的使用情况

### 交互设计

工作流可视化支持丰富的交互功能：

- **步骤导航**：快速跳转到特定智能体的工作阶段
- **展开/折叠**：调整可视化视图的详细程度
- **实时更新**：动态展示正在进行的工作流程

## 状态管理与数据流

### Zustand状态管理

项目使用Zustand进行状态管理，相比Redux更加轻量且易于使用：

```typescript
export const useStore = create<{
  teamMembers: TeamMember[];
  enabledTeamMembers: string[];
  messages: Message[];
  responding: boolean;
  state: {
    messages: { role: string; content: string }[];
  };
}>(() => ({
  teamMembers: [],
  enabledTeamMembers: [],
  messages: [],
  responding: false,
  state: {
    messages: [],
  },
}));
```

主要状态包括：

- **消息历史**：用户与系统的对话记录
- **响应状态**：系统是否正在处理查询
- **团队成员**：可用的智能体及其配置
- **会话状态**：当前会话的完整状态信息

### 数据流转

数据在前端组件和后端服务之间的流转遵循清晰的路径：

1. **用户输入** → InputBox组件收集用户查询和配置
2. **数据发送** → 通过store.sendMessage函数发送到后端
3. **事件流接收** → 接收服务器发送的事件流(SSE)
4. **状态更新** → 更新本地状态以反映后端处理进度
5. **界面渲染** → 根据更新的状态重新渲染界面组件

## 功能特色与用户体验

### 深度思考模式

用户可以启用"深度思考"模式，使系统在分析医疗查询时进行更全面的思考：

```tsx
<Button
  variant="outline"
  className={cn("rounded-2xl px-4 text-sm", {
    "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary/90":
      deepThinkingMode,
    "border-muted bg-muted/50 text-muted-foreground hover:bg-muted/80":
      !deepThinkingMode,
  })}
  onClick={() => {
    setDeepThinkMode(!deepThinkingMode);
  }}
>
  <ExperimentOutlined className="h-4 w-4 mr-1" />
  <span>深度思考</span>
</Button>
```

此功能可以帮助用户获得更深入、更全面的医疗信息分析。

### 联网搜索选项

用户可以控制系统是否在规划前进行联网搜索：

```tsx
<Button
  variant="outline"
  className={cn("rounded-2xl px-4 text-sm", {
    "border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary/90":
      searchBeforePlanning,
    "border-muted bg-muted/50 text-muted-foreground hover:bg-muted/80":
      !searchBeforePlanning,
  })}
  onClick={() => {
    setSearchBeforePlanning(!searchBeforePlanning);
  }}
>
  <GlobalOutlined className="h-4 w-4 mr-1" />
  <span>联网搜索</span>
</Button>
```

此功能允许系统获取最新的医疗信息，提高查询结果的时效性和准确性。

### 智能体团队配置

用户可以自定义启用的智能体组合，根据需求调整查询处理团队：

```tsx
<DropdownMenuCheckboxItem
  key={member.name}
  disabled={!member.is_optional}
  checked={enabledTeamMembers.includes(member.name)}
  onCheckedChange={() => {
    setEnabledTeamMembers(
      enabledTeamMembers.includes(member.name)
        ? enabledTeamMembers.filter(
            (name) => name !== member.name,
          )
        : [...enabledTeamMembers, member.name],
    );
  }}
>
  {member.name.charAt(0).toUpperCase() +
    member.name.slice(1)}
  {member.is_optional && (
    <span className="text-xs text-gray-400">
      (Optional)
    </span>
  )}
</DropdownMenuCheckboxItem>
```

### 实时反馈与交互

系统提供丰富的实时反馈机制：

- **打字动画**：消息生成过程中的实时展示
- **工作流进度**：实时更新智能体的工作状态
- **取消功能**：允许用户在等待时取消长时间查询

## 技术实现细节

### 服务器发送事件(SSE)实现

系统采用SSE技术实现前后端实时通信：

```typescript
export function chatStream(
  userMessage: Message,
  state: { messages: { role: string; content: string }[] },
  params: {
    deepThinkingMode: boolean;
    searchBeforePlanning: boolean;
    teamMembers: string[];
  },
  options: { abortSignal?: AbortSignal } = {},
) {
  return fetchStream<ChatEvent>(
    (env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api") + "/chat/stream",
    {
      body: JSON.stringify({
        messages: [userMessage],
        deep_thinking_mode: params.deepThinkingMode,
        search_before_planning: params.searchBeforePlanning,
        debug: location.search.includes("debug") &&
          !location.search.includes("debug=false"),
        team_members: params.teamMembers,
      }),
      signal: options.abortSignal,
    },
  );
}
```

### 工作流事件处理

前端需要处理多种类型的工作流事件：

- **start_of_workflow**：工作流开始
- **start_of_agent/end_of_agent**：智能体活动开始/结束
- **message**：消息内容更新
- **tool_call/tool_call_result**：工具调用和结果

### 本地存储

系统使用localStorage保存用户偏好设置：

```typescript
const saveConfig = useCallback(() => {
  localStorage.setItem(
    "deepmedical.config.inputbox",
    JSON.stringify({ deepThinkingMode, searchBeforePlanning }),
  );
}, [deepThinkingMode, searchBeforePlanning]);
```

这确保了用户下次访问时能保持相同的配置。

## 未来优化方向

基于当前实现，我们识别了以下几个前端优化方向：

1. **持久化会话**：实现会话历史的持久化存储，允许用户在刷新页面后继续之前的对话
2. **国际化支持**：增强多语言支持，特别是确保始终使用中文响应
3. **反爬虫优化**：改进与后端的协同，提升数据采集的质量和成功率
4. **移动端适配优化**：进一步改善在移动设备上的用户体验
5. **工作流交互增强**：提供更多工作流交互选项，如暂停、调整等
6. **医疗数据可视化**：集成专业医疗数据可视化组件，提升信息呈现质量
