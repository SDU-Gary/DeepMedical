# DeepMedical对话状态持久化实现文档

## 1. 功能概述

对话状态持久化功能允许用户在页面刷新或重新打开应用后，恢复之前的对话内容和状态。这个功能通过以下步骤实现：

1. 后端创建并维护会话(Session)
2. 前端保存会话ID并在刷新后恢复会话
3. 后端保存对话消息和状态
4. 前端从后端获取历史消息和状态

## 2. 数据模型

### 2.1 后端数据模型

后端使用两个主要模型：`Session`和`Message`

```python
# src/models/session.py
class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    state = Column(JSON, nullable=True)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session = relationship("Session", back_populates="messages")
```

### 2.2 前端状态模型

前端使用Zustand管理状态：

```typescript
// src/core/store/store.ts
export const useStore = create<{
  teamMembers: TeamMember[];
  enabledTeamMembers: string[];
  messages: Message[];
  responding: boolean;
  state: {
    messages: { role: string; content: string }[];
  };
  sessionId: string | null;  // 会话ID字段
}>(() => ({
  teamMembers: [],
  enabledTeamMembers: [],
  messages: [],
  responding: false,
  state: {
    messages: [],
  },
  sessionId: null,
}));
```

## 3. 实现流程

### 3.1 会话创建流程

1. 用户首次访问应用时，前端没有会话ID
2. 用户发送第一条消息时，后端创建新会话
3. 后端通过事件流返回会话ID给前端
4. 前端保存会话ID到localStorage

```python
# src/service/workflow_service.py
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
    finally:
        db.close()
else:
    logger.info(f"Using existing session: {session_id}")
```

```typescript
// src/core/store/store.ts
// 处理会话ID事件
if (event.type === "session_id" || (event as any).event === "session_id") {
  const newSessionId = event.data.session_id;
  console.log("Received session_id event:", event);
  
  if (newSessionId) {
    useStore.setState({ sessionId: newSessionId });
    localStorage.setItem("deepmedical.session.id", newSessionId);
    console.log("Session ID saved to localStorage:", newSessionId);
  }
  continue;
}
```

### 3.2 状态保存流程

1. 工作流执行过程中，后端将消息保存到数据库
2. 工作流结束时，后端将最终状态保存到数据库
3. 状态包含完整的消息历史和工作流状态

```python
# src/service/workflow_service.py
# 将最终状态保存到数据库
if session_id:
    try:
        # 获取数据库连接
        from src.database.db import SessionLocal
        db = SessionLocal()
        
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
                        # 其他情况处理...
                else:
                    # 其他字段处理...
        
        # 保存最终状态
        from src.service.session_service import SessionService
        await SessionService.update_session_state(
            db=db, 
            session_id=session_id, 
            state=serializable_state
        )
        logger.info(f"Final state saved to session {session_id}")
    except Exception as e:
        logger.error(f"Error saving final state to session {session_id}: {e}", exc_info=True)
    finally:
        db.close()
```

### 3.3 会话恢复流程

1. 用户刷新页面时，前端从localStorage获取会话ID
2. 前端使用会话ID从后端获取历史消息和状态
3. 前端恢复消息历史和状态

```typescript
// src/core/store/store.ts
export function useInitSession() {
  console.log("useInitSession hook called");
  
  useEffect(() => {
    console.log("useInitSession effect running");
    
    // 从localStorage获取sessionId
    const sessionId = localStorage.getItem("deepmedical.session.id");
    console.log("localStorage sessionId:", sessionId);
    
    if (sessionId) {
      console.log("Attempting to restore session:", sessionId);
      
      // 设置sessionId
      useStore.setState({ sessionId });
      console.log("SessionId set in store");
      
      // 从后端加载会话历史
      const apiUrl = env?.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
      const historyUrl = `${apiUrl}/session/${sessionId}/history`;
      console.log("Fetching session history from:", historyUrl);
      
      fetch(historyUrl)
        .then((res) => {
          console.log("Session history response status:", res.status);
          if (!res.ok) {
            throw new Error(`Failed to load session history: ${res.status}`);
          }
          return res.json();
        })
        .then((data) => {
          console.log("Session data received:", data);
          
          // 确保messages数组存在且格式正确
          if (Array.isArray(data.messages) && data.messages.length > 0) {
            // 准备要恢复的状态
            let stateToRestore = { messages: [] };
            
            // 处理后端返回的状态
            if (data.state) {
              // 检查状态是否包含messages数组
              if (data.state.messages && Array.isArray(data.state.messages)) {
                stateToRestore = data.state;
              } else {
                // 如果没有messages数组，构造一个包含消息的状态
                stateToRestore = {
                  ...data.state,
                  messages: data.messages.map((msg: any) => ({
                    role: msg.role,
                    content: msg.content
                  }))
                };
              }
            }
            
            // 恢复消息历史和状态
            useStore.setState({ 
              messages: data.messages,
              state: stateToRestore
            });
            console.log("Session restored successfully with", data.messages.length, "messages");
          } else {
            console.warn("Session has no messages or invalid format");
            localStorage.removeItem("deepmedical.session.id");
            useStore.setState({ sessionId: null });
          }
        })
        .catch((err) => {
          console.error("Error loading session history:", err);
          localStorage.removeItem("deepmedical.session.id");
          useStore.setState({ sessionId: null });
        });
    }
  }, []);
}
```

## 4. API接口

### 4.1 创建会话

```
POST /api/session
Request: { "user_id": "optional_user_id" }
Response: { "id": "session_id", "created_at": "timestamp", "updated_at": "timestamp" }
```

### 4.2 获取会话历史

```
GET /api/session/{session_id}/history
Response: {
  "session_id": "session_id",
  "messages": [
    {
      "id": "message_id",
      "role": "user|assistant",
      "type": "text",
      "content": "message content",
      "created_at": "timestamp"
    }
  ],
  "state": {
    "messages": [...],
    ... 其他状态数据
  }
}
```

### 4.3 聊天流接口

```
POST /api/chat/stream
Request: {
  "messages": [{ "role": "user", "content": "message" }],
  "deep_thinking_mode": false,
  "search_before_planning": false,
  "debug": false,
  "team_members": ["member1", "member2"],
  "session_id": "optional_session_id"
}
Response: SSE事件流，包含多种事件类型
```

## 5. 事件流格式

后端发送的事件流使用SSE格式：

```
event: event_type
data: {"key": "value"}

```

主要事件类型包括：

1. `session_id`: 返回会话ID
2. `start_of_agent`: 代理开始工作
3. `end_of_agent`: 代理结束工作
4. `message`: 消息内容更新
5. `final_session_state`: 最终会话状态

前端解析事件流的代码：

```typescript
// src/core/sse/fetch-stream.ts
function parseEvent<T extends StreamEvent>(chunk: string) {
  let resultType = "message";
  let resultData: object | null = null;
  for (const line of chunk.split("\n")) {
    const pos = line.indexOf(": ");
    if (pos === -1) {
      continue;
    }
    const key = line.slice(0, pos);
    const value = line.slice(pos + 2);
    if (key === "event") {
      resultType = value;
    } else if (key === "data") {
      resultData = JSON.parse(value);
    }
  }
  if (resultType === "message" && resultData === null) {
    return undefined;
  }
  return {
    type: resultType,
    data: resultData,
  } as T;
}
```

## 6. 数据流向图

```
┌────────────┐         ┌────────────┐         ┌────────────┐
│            │  1. 创建会话  │            │  2. 保存会话ID │            │
│   后端     │ ────────> │   前端     │ ────────> │ localStorage │
│            │         │            │         │            │
└────────────┘         └────────────┘         └────────────┘
      │                      │                      │
      │                      │                      │
      │                      │                      │
      │                      │                      │
      │                      │                      │
      ▼                      ▼                      ▼
┌────────────┐         ┌────────────┐         ┌────────────┐
│            │  3. 保存状态  │            │  4. 刷新页面   │            │
│  数据库    │ <──────── │   后端     │ <──────── │   前端     │
│            │         │            │         │            │
└────────────┘         └────────────┘         └────────────┘
      │                      │                      │
      │                      │                      │
      │                      │                      │
      │                      │                      │
      │                      │                      │
      ▼                      ▼                      ▼
┌────────────┐         ┌────────────┐         ┌────────────┐
│            │  5. 获取历史  │            │  6. 恢复状态   │            │
│  数据库    │ ────────> │   后端     │ ────────> │   前端     │
│            │         │            │         │            │
└────────────┘         └────────────┘         └────────────┘
```

## 7. 当前问题与解决尝试

### 7.1 当前问题

目前，对话状态持久化功能存在以下问题：

1. **会话ID保存问题**：
   - 后端能够成功创建会话并保存状态到数据库
   - 但前端无法接收到会话ID事件，导致localStorage中没有保存sessionId
   - 刷新页面后，前端日志显示`localStorage sessionId: null`

2. **状态恢复问题**：
   - 由于没有会话ID，前端无法从后端获取历史消息和状态
   - 刷新页面后，对话状态丢失，返回到初始界面

3. **事件处理问题**：
   - 前端控制台没有显示会话ID事件相关的日志
   - 没有看到`Session ID saved to localStorage`和`Verified sessionId in localStorage`的输出

### 7.2 解决尝试

#### 尝试1：修复后端状态序列化问题

发现后端保存状态时存在序列化问题，`HumanMessage`对象无法被JSON序列化：

```
Error updating session state: (builtins.TypeError) Object of type HumanMessage is not JSON serializable
```

修复方案：
```python
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
                # 其他情况处理...
```

结果：后端成功保存状态到数据库，但前端仍然无法恢复会话。

#### 尝试2：增强前端会话恢复逻辑

修改前端的`useInitSession`函数，增强状态恢复逻辑：

```typescript
// 准备要恢复的状态
let stateToRestore = { messages: [] };

// 处理后端返回的状态
if (data.state) {
  // 检查状态是否包含messages数组
  if (data.state.messages && Array.isArray(data.state.messages)) {
    stateToRestore = data.state;
  } else {
    // 如果没有messages数组，构造一个包含消息的状态
    stateToRestore = {
      ...data.state,
      messages: data.messages.map((msg: any) => ({
        role: msg.role,
        content: msg.content
      }))
    };
  }
}
```

结果：前端状态恢复逻辑更加健壮，但由于localStorage中没有sessionId，仍然无法恢复会话。

#### 尝试3：增强前端会话ID事件处理

修改前端处理会话ID事件的逻辑，兼容不同的事件格式：

```typescript
// 处理会话ID事件，兼容两种事件格式
if (event.type === "session_id" || (event as any).event === "session_id") {
  const newSessionId = event.data.session_id;
  console.log("Received session_id event:", event);
  
  if (newSessionId) {
    useStore.setState({ sessionId: newSessionId });
    localStorage.setItem("deepmedical.session.id", newSessionId);
    console.log("Session ID saved to localStorage:", newSessionId);
    
    // 验证保存是否成功
    const savedId = localStorage.getItem("deepmedical.session.id");
    console.log("Verified sessionId in localStorage:", savedId);
  } else {
    console.warn("Received session_id event but sessionId is empty");
  }
  continue; // 处理完会话ID事件后继续处理其他事件
}
```

结果：前端事件处理逻辑更加健壮，但仍然没有接收到会话ID事件。

#### 尝试4：修改后端事件发送格式

修改后端API中的事件发送逻辑，确保会话ID事件使用正确的格式：

```python
# 在最后一个事件后返回session_id
if session_id:
    # 确保使用正确的事件格式，与前端的期望一致
    # 前端的SSE解析逻辑会将event字段解析为前端对象的type字段
    yield {
        "event": "session_id",  # 这里的event字段会被前端解析为type字段
        "data": json.dumps({"session_id": session_id}, ensure_ascii=False),
    }
    print(f"Sent session_id event with session_id: {session_id}")
```

结果：后端发送的事件格式更加规范，但前端仍然没有接收到会话ID事件。

### 7.3 可能的问题原因

1. **事件流格式不匹配**：
   - 后端发送的事件格式可能与前端期望的不一致
   - 前端的SSE解析逻辑可能无法正确解析后端发送的事件

2. **事件处理时序问题**：
   - 后端在工作流结束时才发送会话ID事件
   - 如果用户在工作流完全结束前刷新页面，可能会导致会话ID未被保存

3. **React开发环境问题**：
   - React的严格模式可能导致钩子执行多次
   - 开发环境的热重载可能干扰事件流处理

4. **浏览器存储问题**：
   - 浏览器可能限制了localStorage的访问
   - 隐私模式或特定浏览器设置可能阻止localStorage的使用

## 8. 进一步调试建议

### 8.1 前端调试

1. **添加更详细的事件日志**：
   ```typescript
   // 在for await循环开始处添加
   console.log("Raw event received:", event);
   ```

2. **验证localStorage访问**：
   ```typescript
   // 在页面加载时测试localStorage
   try {
     localStorage.setItem("test", "test");
     const test = localStorage.getItem("test");
     console.log("localStorage test:", test);
     localStorage.removeItem("test");
   } catch (e) {
     console.error("localStorage access error:", e);
   }
   ```

3. **检查事件流连接**：
   ```typescript
   // 在fetchStream函数中添加
   console.log("Starting SSE connection to:", url);
   ```

### 8.2 后端调试

1. **添加详细的事件日志**：
   ```python
   # 在发送事件前添加
   event_data = {
       "event": "session_id",
       "data": json.dumps({"session_id": session_id}, ensure_ascii=False),
   }
   logger.info(f"Sending event: {event_data}")
   yield event_data
   ```

2. **在工作流早期发送会话ID**：
   ```python
   # 在创建会话后立即发送会话ID事件
   if session_id:
       yield {
           "event": "session_id",
           "data": json.dumps({"session_id": session_id}, ensure_ascii=False),
       }
       logger.info(f"Sent early session_id event: {session_id}")
   ```

3. **验证SSE格式**：
   ```python
   # 确保发送的是正确的SSE格式
   yield {
       "event": "session_id",
       "data": json.dumps({"session_id": session_id}, ensure_ascii=False),
   }
   ```

### 8.3 网络调试

1. **使用浏览器开发者工具**：
   - 检查Network面板中的事件流请求
   - 查看事件流的响应内容
   - 验证事件流是否包含会话ID事件

2. **使用curl测试事件流**：
   ```bash
   curl -N -H "Accept: text/event-stream" -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"test"}]}' \
     http://localhost:8000/api/chat/stream
   ```

## 9. 总结

对话状态持久化功能的实现涉及前后端多个组件的协作，当前主要问题是前端无法接收到会话ID事件，导致localStorage中没有保存sessionId，从而无法恢复会话状态。

我们已经尝试了多种解决方案，包括修复后端状态序列化问题、增强前端会话恢复逻辑、增强前端会话ID事件处理、修改后端事件发送格式等，但问题仍未解决。

进一步的调试应该集中在事件流的格式和处理上，确保后端发送的事件能够被前端正确接收和处理。同时，也需要验证localStorage的访问和使用是否正常。
