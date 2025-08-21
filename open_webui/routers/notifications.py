"""
通知系统路由器
提供通知相关的API接口
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from open_webui.models.notifications import (
    Notifications,
    NotificationResponse,
    CreateNotificationForm,
)
from open_webui.utils.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

log = logging.getLogger(__name__)


####################
# Request Models
####################

class MarkReadRequest(BaseModel):
    """标记已读请求"""
    notification_id: str


class BatchMarkReadRequest(BaseModel):
    """批量标记已读请求"""
    notification_ids: List[str]


####################
# GET /notifications - 获取通知列表
####################

@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user=Depends(get_current_user)
):
    """
    获取用户通知列表
    
    Args:
        limit: 每页数量，默认50，最大100
        offset: 偏移量，用于分页
        unread_only: 是否只返回未读通知
    """
    notifications = Notifications.get_notifications_by_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only
    )
    
    return [
        NotificationResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            type=n.type,
            priority=n.priority,
            read=n.read,
            metadata=n.metadata,
            created_at=n.created_at,
            read_at=n.read_at
        )
        for n in notifications
    ]


####################
# GET /notifications/unread-count - 获取未读数量
####################

@router.get("/unread-count", response_model=dict)
async def get_unread_count(current_user=Depends(get_current_user)):
    """获取未读通知数量"""
    count = Notifications.get_unread_count(current_user.id)
    return {"count": count}


####################
# POST /notifications/{id}/read - 标记单个通知为已读
####################

@router.post("/{notification_id}/read", response_model=dict)
async def mark_notification_as_read(
    notification_id: str,
    current_user=Depends(get_current_user)
):
    """标记单个通知为已读"""
    success = Notifications.mark_as_read(notification_id, current_user.id)
    
    if success:
        return {"status": True, "message": "Notification marked as read"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read"
        )


####################
# POST /notifications/batch/read - 批量标记为已读
####################

@router.post("/batch/read", response_model=dict)
async def mark_batch_as_read(
    request: BatchMarkReadRequest,
    current_user=Depends(get_current_user)
):
    """批量标记通知为已读"""
    if not request.notification_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No notification IDs provided"
        )
    
    count = Notifications.mark_batch_as_read(
        notification_ids=request.notification_ids,
        user_id=current_user.id
    )
    
    return {
        "status": True,
        "message": f"Marked {count} notifications as read",
        "count": count
    }


####################
# POST /notifications/all/read - 标记所有为已读
####################

@router.post("/all/read", response_model=dict)
async def mark_all_as_read(current_user=Depends(get_current_user)):
    """标记用户所有通知为已读"""
    count = Notifications.mark_all_as_read(current_user.id)
    
    return {
        "status": True,
        "message": f"Marked {count} notifications as read",
        "count": count
    }


####################
# DELETE /notifications/{id} - 删除通知
####################

@router.delete("/{notification_id}", response_model=dict)
async def delete_notification(
    notification_id: str,
    current_user=Depends(get_current_user)
):
    """删除单个通知"""
    success = Notifications.delete_notification(notification_id, current_user.id)
    
    if success:
        return {"status": True, "message": "Notification deleted"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )


####################
# POST /notifications - 创建通知（内部使用）
####################

@router.post("", response_model=NotificationResponse)
async def create_notification(
    form_data: CreateNotificationForm,
    current_user=Depends(get_current_user)
):
    """
    创建新通知（通常由系统内部调用）
    只有管理员可以创建通知
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create notifications"
        )
    
    notification = Notifications.insert_notification(
        user_id=form_data.user_id,
        title=form_data.title,
        content=form_data.content,
        type=form_data.type,
        priority=form_data.priority,
        metadata=form_data.metadata
    )
    
    if notification:
        return NotificationResponse(
            id=notification.id,
            title=notification.title,
            content=notification.content,
            type=notification.type,
            priority=notification.priority,
            read=notification.read,
            metadata=notification.metadata,
            created_at=notification.created_at,
            read_at=notification.read_at
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification"
        )
