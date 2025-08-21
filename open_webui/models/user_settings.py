"""
用户设置数据模型

定义用户个性化配置的数据结构。
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer
from open_webui.internal.db import Base, get_db


class UserSettings(Base):
    """用户设置模型"""
    __tablename__ = "user_settings"

    user_id = Column(String, ForeignKey("user.id"), primary_key=True)
    
    # 主题设置
    theme = Column(String, default="system")  # light, dark, system
    
    # 通知偏好设置
    notifications = Column(JSON, default=lambda: {
        "solution": True,    # 解决方案生成通知
        "mention": False,    # 提及通知  
        "system": True       # 系统通知
    })
    
    # 其他个性化配置
    preferences = Column(JSON, default=lambda: {
        "language": "zh-cn",
        "autoSave": True,
        "showHints": True,
        "fontSize": "medium",
        "sidebarCollapsed": False,
        "codeTheme": "monokai"
    })
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSettingsModel(BaseModel):
    """用户设置Pydantic模型"""
    theme: str = Field(default="system", description="主题设置")
    notifications: Dict[str, bool] = Field(
        default={
            "solution": True,
            "mention": False,
            "system": True
        },
        description="通知偏好"
    )
    preferences: Dict[str, Any] = Field(
        default={
            "language": "zh-cn",
            "autoSave": True,
            "showHints": True,
            "fontSize": "medium",
            "sidebarCollapsed": False,
            "codeTheme": "monokai"
        },
        description="用户偏好"
    )
    updated_at: Optional[datetime] = None


class UserSettingsUpdateModel(BaseModel):
    """用户设置更新模型"""
    theme: Optional[str] = None
    notifications: Optional[Dict[str, bool]] = None
    preferences: Optional[Dict[str, Any]] = None


class UserSettingsTable:
    """用户设置数据表操作类"""
    
    def get_user_settings(self, user_id: str) -> Optional[UserSettingsModel]:
        """获取用户设置"""
        with get_db() as db:
            settings = db.query(UserSettings).filter_by(user_id=user_id).first()
            if settings:
                return UserSettingsModel(
                    theme=settings.theme,
                    notifications=settings.notifications or {
                        "solution": True,
                        "mention": False,
                        "system": True
                    },
                    preferences=settings.preferences or {
                        "language": "zh-cn",
                        "autoSave": True,
                        "showHints": True,
                        "fontSize": "medium",
                        "sidebarCollapsed": False,
                        "codeTheme": "monokai"
                    },
                    updated_at=settings.updated_at
                )
            return None
    
    def get_or_create_user_settings(self, user_id: str) -> UserSettingsModel:
        """获取或创建用户设置"""
        with get_db() as db:
            settings = db.query(UserSettings).filter_by(user_id=user_id).first()
            if not settings:
                settings = UserSettings(user_id=user_id)
                db.add(settings)
                db.commit()
                db.refresh(settings)
            
            return UserSettingsModel(
                theme=settings.theme,
                notifications=settings.notifications or {
                    "solution": True,
                    "mention": False,
                    "system": True
                },
                preferences=settings.preferences or {
                    "language": "zh-cn",
                    "autoSave": True,
                    "showHints": True,
                    "fontSize": "medium",
                    "sidebarCollapsed": False,
                    "codeTheme": "monokai"
                },
                updated_at=settings.updated_at
            )
    
    def update_user_settings(
        self, 
        user_id: str, 
        update_data: UserSettingsUpdateModel
    ) -> Optional[UserSettingsModel]:
        """更新用户设置"""
        with get_db() as db:
            settings = db.query(UserSettings).filter_by(user_id=user_id).first()
            if not settings:
                # 如果不存在，创建新的设置
                settings = UserSettings(user_id=user_id)
                db.add(settings)
            
            # 更新字段
            if update_data.theme is not None:
                settings.theme = update_data.theme
            if update_data.notifications is not None:
                settings.notifications = update_data.notifications
            if update_data.preferences is not None:
                settings.preferences = update_data.preferences
            
            settings.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(settings)
            
            return UserSettingsModel(
                theme=settings.theme,
                notifications=settings.notifications,
                preferences=settings.preferences,
                updated_at=settings.updated_at
            )
    
    def update_theme(self, user_id: str, theme: str) -> bool:
        """更新主题设置"""
        with get_db() as db:
            settings = db.query(UserSettings).filter_by(user_id=user_id).first()
            if not settings:
                settings = UserSettings(user_id=user_id)
                db.add(settings)
            
            settings.theme = theme
            settings.updated_at = datetime.utcnow()
            db.commit()
            return True
    
    def update_notification_preference(
        self, 
        user_id: str, 
        notification_type: str, 
        enabled: bool
    ) -> bool:
        """更新通知偏好"""
        with get_db() as db:
            settings = db.query(UserSettings).filter_by(user_id=user_id).first()
            if not settings:
                settings = UserSettings(user_id=user_id)
                db.add(settings)
            
            if settings.notifications is None:
                settings.notifications = {}
            
            settings.notifications[notification_type] = enabled
            settings.updated_at = datetime.utcnow()
            db.commit()
            return True
    
    def delete_user_settings(self, user_id: str) -> bool:
        """删除用户设置"""
        with get_db() as db:
            settings = db.query(UserSettings).filter_by(user_id=user_id).first()
            if settings:
                db.delete(settings)
                db.commit()
                return True
            return False


# 创建全局实例
UserSettingsManager = UserSettingsTable()
