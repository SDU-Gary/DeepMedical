import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.session import Session as SessionModel, Message as MessageModel

logger = logging.getLogger(__name__)

class SessionService:
    """会话服务，处理会话和消息的CRUD操作"""
    
    @staticmethod
    async def create_session(db: Session, user_id: Optional[str] = None) -> SessionModel:
        """创建新会话"""
        try:
            session = SessionModel(user_id=user_id)
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"Created new session with ID: {session.id}")
            return session
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating session: {e}")
            raise
    
    @staticmethod
    async def get_session(db: Session, session_id: str) -> Optional[SessionModel]:
        """获取会话"""
        try:
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if session:
                logger.debug(f"Retrieved session with ID: {session_id}")
            else:
                logger.warning(f"Session with ID {session_id} not found")
            return session
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            raise
    
    @staticmethod
    async def update_session_state(db: Session, session_id: str, state: Dict[str, Any]) -> SessionModel:
        """更新会话状态"""
        try:
            session = await SessionService.get_session(db, session_id)
            if not session:
                logger.error(f"Cannot update state: Session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            
            session.state = state
            session.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
            logger.info(f"Updated state for session {session_id}")
            return session
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating session state for {session_id}: {e}")
            raise
    
    @staticmethod
    async def add_message(
        db: Session, 
        session_id: str, 
        role: str, 
        content: Any,
        message_type: str = "text"  # 默认为文本类型
    ) -> MessageModel:
        """添加消息到会话
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            role: 消息角色（user或assistant）
            content: 消息内容
            message_type: 消息类型，默认为"text"
            
        Returns:
            创建的消息对象
        """
        try:
            session = await SessionService.get_session(db, session_id)
            if not session:
                logger.error(f"Cannot add message: Session {session_id} not found")
                raise ValueError(f"Session {session_id} not found")
            
            # 如果content不是字符串，转为JSON字符串
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
                
            message = MessageModel(
                session_id=session_id,
                role=role,
                type=message_type,
                content=content
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            logger.debug(f"Added {role} message to session {session_id}")
            return message
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding message to session {session_id}: {e}")
            raise
    
    @staticmethod
    async def get_session_messages(db: Session, session_id: str) -> List[MessageModel]:
        """获取会话的所有消息"""
        try:
            messages = db.query(MessageModel).filter(
                MessageModel.session_id == session_id
            ).order_by(MessageModel.created_at).all()
            logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages
        except Exception as e:
            logger.error(f"Error retrieving messages for session {session_id}: {e}")
            raise
    
    @staticmethod
    async def format_messages_for_frontend(messages: List[MessageModel]) -> List[Dict]:
        """将消息格式化为前端需要的格式"""
        try:
            formatted_messages = []
            for msg in messages:
                try:
                    # 尝试解析JSON内容
                    content = json.loads(msg.content)
                except json.JSONDecodeError:
                    # 如果不是JSON，直接使用原始内容
                    content = msg.content
                    
                formatted_messages.append({
                    "id": msg.id,
                    "role": msg.role,
                    "type": msg.type,
                    "content": content
                })
            logger.debug(f"Formatted {len(messages)} messages for frontend")
            return formatted_messages
        except Exception as e:
            logger.error(f"Error formatting messages for frontend: {e}")
            raise