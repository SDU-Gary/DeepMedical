from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid
import logging
from datetime import datetime, timezone

from src.database.db import Base

logger = logging.getLogger(__name__)

class Session(Base):
    """会话模型，用于存储用户会话信息"""
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(50), nullable=True, index=True)  # 可选，用于关联用户
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # 存储完整的会话状态
    state = Column(JSON, nullable=True)  # 存储完整的会话状态
    
    # 关联消息 
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    """消息模型，用于存储会话中的消息"""
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    type = Column(String(20), nullable=False)  # text, workflow
    content = Column(Text, nullable=False)  # 消息内容
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # 关联会话
    session = relationship("Session", back_populates="messages")