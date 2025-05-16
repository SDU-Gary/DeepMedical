# DeepMedical 数据库文档

## 概述

DeepMedical项目使用SQLAlchemy作为ORM（对象关系映射）工具，默认采用SQLite作为数据库引擎。数据库主要用于存储用户会话信息、消息历史和会话状态，实现对话的持久化和跨设备同步。

## 数据库配置

### 基本配置

数据库配置位于 `src/database/db.py` 文件中：

```python
# 数据库URL，可从环境变量获取或使用默认值
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./deepmedical.db")

# 创建数据库引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()
```

### 配置说明

- **数据库类型**：默认使用SQLite，存储在项目根目录的`deepmedical.db`文件中
- **环境变量**：可通过`DATABASE_URL`环境变量自定义数据库连接字符串
- **线程安全**：SQLite配置了`check_same_thread=False`，允许多线程访问
- **事务控制**：默认不自动提交(`autocommit=False`)和不自动刷新(`autoflush=False`)

## 数据模型

数据模型定义在`src/models/session.py`文件中，主要包含两个模型：`Session`和`Message`。

### Session模型

`Session`模型用于存储用户会话信息：

```python
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    state = Column(JSON, nullable=True)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
```

#### 字段说明

| 字段名 | 类型 | 说明 | 默认值 |
|-------|------|------|-------|
| id | String(36) | 主键，会话唯一标识 | UUID生成 |
| user_id | String(50) | 用户ID，可为空，建立索引 | NULL |
| created_at | DateTime | 创建时间，UTC时区 | 当前UTC时间 |
| updated_at | DateTime | 更新时间，UTC时区 | 当前UTC时间，自动更新 |
| state | JSON | 会话状态，存储工作流状态 | NULL |

#### 关系

- **messages**: 一对多关系，关联到`Message`模型
  - `cascade="all, delete-orphan"`: 删除会话时级联删除相关消息

### Message模型

`Message`模型用于存储会话中的消息：

```python
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

#### 字段说明

| 字段名 | 类型 | 说明 | 默认值 |
|-------|------|------|-------|
| id | String(36) | 主键，消息唯一标识 | UUID生成 |
| session_id | String(36) | 外键，关联到sessions表的id | 无，必填 |
| role | String(20) | 消息角色，如"user"或"assistant" | 无，必填 |
| type | String(20) | 消息类型，如"text"或"workflow" | 无，必填 |
| content | Text | 消息内容，存储为文本 | 无，必填 |
| created_at | DateTime | 创建时间，UTC时区 | 当前UTC时间 |

#### 关系

- **session**: 多对一关系，关联到`Session`模型

## 数据库操作

数据库操作主要通过`src/service/session_service.py`中的`SessionService`类实现：

### 主要方法

1. **创建会话**
   ```python
   async def create_session(db: Session, user_id: Optional[str] = None) -> SessionModel
   ```

2. **获取会话**
   ```python
   async def get_session(db: Session, session_id: str) -> Optional[SessionModel]
   ```

3. **更新会话状态**
   ```python
   async def update_session_state(db: Session, session_id: str, state: Dict[str, Any]) -> SessionModel
   ```

4. **添加消息**
   ```python
   async def add_message(db: Session, session_id: str, role: str, message_type: str, content: Any) -> MessageModel
   ```

5. **获取会话消息**
   ```python
   async def get_session_messages(db: Session, session_id: str) -> List[MessageModel]
   ```

6. **格式化消息**
   ```python
   async def format_messages_for_frontend(messages: List[MessageModel]) -> List[Dict]
   ```

## API接口

与数据库相关的API接口定义在`src/api/app.py`文件中：

### 会话相关接口

1. **创建会话**
   - 路径: `/api/session`
   - 方法: POST
   - 参数: `CreateSessionRequest`(可选user_id)
   - 返回: `SessionResponse`(id, created_at, updated_at)

2. **获取会话历史**
   - 路径: `/api/session/{session_id}/history`
   - 方法: GET
   - 参数: 路径参数`session_id`
   - 返回: `SessionHistoryResponse`(session_id, messages, state)

3. **聊天流接口**
   - 路径: `/api/chat/stream`
   - 方法: POST
   - 参数: `ChatRequest`(包含可选的session_id)
   - 返回: 事件流，包含`session_id`事件

## 数据库迁移

数据库结构变更通过手动迁移脚本实现。当模型发生变化时，需要更新迁移脚本并执行。

## 时区处理

所有时间戳均采用UTC时区，使用`datetime.now(timezone.utc)`生成，确保时区一致性和可移植性。

## 数据安全

1. **数据验证**: 使用Pydantic模型进行输入验证
2. **事务管理**: 使用try/except/finally确保事务完整性
3. **错误处理**: 详细的日志记录和异常处理

## 最佳实践

1. **连接管理**: 使用`get_db`依赖注入确保连接正确关闭
2. **查询优化**: 为频繁查询的字段(如user_id)建立索引
3. **状态序列化**: JSON字段用于存储复杂的状态数据
4. **级联删除**: 使用`cascade="all, delete-orphan"`确保数据一致性

## 调试与监控

可使用以下工具查看和调试数据库内容：
- DB Browser for SQLite
- VSCode SQLite插件
- DBeaver等通用数据库管理工具

## 未来扩展

1. **用户系统集成**: 扩展user_id字段，与用户认证系统集成
2. **会话管理功能**: 添加会话标题、标签等元数据
3. **分页加载**: 对大量消息实现分页加载
4. **数据分析**: 添加用户行为分析和使用统计功能
