"""
通知系统数据模型
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from open_webui.internal.db import Base, get_db
from open_webui.env import SRC_LOG_LEVELS
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, String, Text, DateTime, Integer, func

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


####################
# DB MODEL
####################

class Notification(Base):
    """通知数据表"""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String, default="info")  # info, success, warning, error
    priority = Column(Integer, default=0)  # 0=normal, 1=high, 2=urgent
    read = Column(Boolean, default=False, index=True)
    extra_data = Column(Text)  # JSON string for additional data
    created_at = Column(DateTime, default=func.now())
    read_at = Column(DateTime, nullable=True)


####################
# Pydantic Models
####################

class NotificationModel(BaseModel):
    """通知数据模型"""
    id: str
    user_id: str
    title: str
    content: str
    type: str = "info"
    priority: int = 0
    read: bool = False
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    read_at: Optional[datetime] = None


class CreateNotificationForm(BaseModel):
    """创建通知表单"""
    user_id: str
    title: str
    content: str
    type: str = "info"
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None


class NotificationResponse(BaseModel):
    """通知响应模型"""
    id: str
    title: str
    content: str
    type: str
    priority: int
    read: bool
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    read_at: Optional[datetime]


####################
# Database Operations
####################

class NotificationsTable:
    """通知表操作类"""
    
    def insert_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        type: str = "info",
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[NotificationModel]:
        """创建新通知"""
        with get_db() as db:
            try:
                notification_id = str(uuid.uuid4())
                
                notification = Notification(
                    id=notification_id,
                    user_id=user_id,
                    title=title,
                    content=content,
                    type=type,
                    priority=priority,
                    read=False,
                    extra_data=json.dumps(metadata) if metadata else None,
                    created_at=datetime.utcnow()
                )
                
                db.add(notification)
                db.commit()
                db.refresh(notification)
                
                return self._to_model(notification)
            except Exception as e:
                log.error(f"Error creating notification: {e}")
                db.rollback()
                return None
    
    def get_notification_by_id(self, notification_id: str) -> Optional[NotificationModel]:
        """根据ID获取通知"""
        with get_db() as db:
            try:
                notification = db.query(Notification).filter_by(id=notification_id).first()
                return self._to_model(notification) if notification else None
            except Exception as e:
                log.error(f"Error getting notification: {e}")
                return None
    
    def get_notifications_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> List[NotificationModel]:
        """获取用户的通知列表"""
        with get_db() as db:
            try:
                query = db.query(Notification).filter_by(user_id=user_id)
                
                if unread_only:
                    query = query.filter_by(read=False)
                
                notifications = (
                    query.order_by(Notification.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                    .all()
                )
                
                return [self._to_model(n) for n in notifications]
            except Exception as e:
                log.error(f"Error getting notifications: {e}")
                return []
    
    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """标记通知为已读"""
        with get_db() as db:
            try:
                result = (
                    db.query(Notification)
                    .filter_by(id=notification_id, user_id=user_id)
                    .update({
                        "read": True,
                        "read_at": datetime.utcnow()
                    })
                )
                db.commit()
                return result > 0
            except Exception as e:
                log.error(f"Error marking notification as read: {e}")
                db.rollback()
                return False
    
    def mark_all_as_read(self, user_id: str) -> int:
        """标记用户所有通知为已读"""
        with get_db() as db:
            try:
                result = (
                    db.query(Notification)
                    .filter_by(user_id=user_id, read=False)
                    .update({
                        "read": True,
                        "read_at": datetime.utcnow()
                    })
                )
                db.commit()
                return result
            except Exception as e:
                log.error(f"Error marking all notifications as read: {e}")
                db.rollback()
                return 0
    
    def mark_batch_as_read(self, notification_ids: List[str], user_id: str) -> int:
        """批量标记通知为已读"""
        with get_db() as db:
            try:
                result = (
                    db.query(Notification)
                    .filter(
                        Notification.id.in_(notification_ids),
                        Notification.user_id == user_id,
                        Notification.read == False
                    )
                    .update({
                        "read": True,
                        "read_at": datetime.utcnow()
                    }, synchronize_session=False)
                )
                db.commit()
                return result
            except Exception as e:
                log.error(f"Error marking batch notifications as read: {e}")
                db.rollback()
                return 0
    
    def get_unread_count(self, user_id: str) -> int:
        """获取未读通知数量"""
        with get_db() as db:
            try:
                count = (
                    db.query(func.count(Notification.id))
                    .filter_by(user_id=user_id, read=False)
                    .scalar()
                )
                return count or 0
            except Exception as e:
                log.error(f"Error getting unread count: {e}")
                return 0
    
    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """删除通知"""
        with get_db() as db:
            try:
                result = (
                    db.query(Notification)
                    .filter_by(id=notification_id, user_id=user_id)
                    .delete()
                )
                db.commit()
                return result > 0
            except Exception as e:
                log.error(f"Error deleting notification: {e}")
                db.rollback()
                return False
    
    def delete_old_notifications(self, days: int = 30) -> int:
        """删除超过指定天数的已读通知"""
        from datetime import timedelta
        with get_db() as db:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                result = (
                    db.query(Notification)
                    .filter(
                        Notification.read == True,
                        Notification.read_at < cutoff_date
                    )
                    .delete()
                )
                db.commit()
                return result
            except Exception as e:
                log.error(f"Error deleting old notifications: {e}")
                db.rollback()
                return 0
    
    def _to_model(self, notification: Notification) -> NotificationModel:
        """将数据库模型转换为Pydantic模型"""
        if not notification:
            return None
        
        metadata = None
        if notification.extra_data:
            try:
                metadata = json.loads(notification.extra_data)
            except:
                metadata = None
        
        return NotificationModel(
            id=notification.id,
            user_id=notification.user_id,
            title=notification.title,
            content=notification.content,
            type=notification.type,
            priority=notification.priority,
            read=notification.read,
            metadata=metadata,
            created_at=notification.created_at,
            read_at=notification.read_at
        )


# 创建单例实例
Notifications = NotificationsTable()
