"""
用户设置API路由

处理用户个性化配置相关的API请求。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from open_webui.models.user_settings import (
    UserSettingsModel,
    UserSettingsUpdateModel,
    UserSettingsManager
)
from open_webui.utils.auth import get_verified_user
from open_webui.models.users import Users


router = APIRouter(prefix="/api/v1/user", tags=["user"])


class ThemeUpdateRequest(BaseModel):
    """主题更新请求"""
    theme: str = Field(..., description="主题名称: light, dark, system")


class NotificationPreferenceRequest(BaseModel):
    """通知偏好更新请求"""
    type: str = Field(..., description="通知类型")
    enabled: bool = Field(..., description="是否启用")


class PreferencesUpdateRequest(BaseModel):
    """用户偏好更新请求"""
    preferences: Dict[str, Any] = Field(..., description="偏好设置")


@router.get("/settings", response_model=UserSettingsModel)
async def get_user_settings(user=Depends(get_verified_user)):
    """
    获取用户设置
    
    Returns:
        UserSettingsModel: 用户设置信息
    """
    try:
        settings = UserSettingsManager.get_or_create_user_settings(user.id)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户设置失败: {str(e)}"
        )


@router.put("/settings", response_model=UserSettingsModel)
async def update_user_settings(
    update_data: UserSettingsUpdateModel,
    user=Depends(get_verified_user)
):
    """
    更新用户设置
    
    Args:
        update_data: 更新的设置数据
        
    Returns:
        UserSettingsModel: 更新后的用户设置
    """
    try:
        settings = UserSettingsManager.update_user_settings(user.id, update_data)
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户设置不存在"
            )
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户设置失败: {str(e)}"
        )


@router.get("/preferences")
async def get_user_preferences(user=Depends(get_verified_user)):
    """
    获取用户偏好设置
    
    Returns:
        dict: 用户偏好设置
    """
    try:
        settings = UserSettingsManager.get_or_create_user_settings(user.id)
        return {
            "code": 200,
            "status": "success",
            "data": settings.preferences
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户偏好失败: {str(e)}"
        )


@router.put("/preferences")
async def update_user_preferences(
    request: PreferencesUpdateRequest,
    user=Depends(get_verified_user)
):
    """
    更新用户偏好设置
    
    Args:
        request: 偏好设置更新请求
        
    Returns:
        dict: 更新结果
    """
    try:
        update_data = UserSettingsUpdateModel(preferences=request.preferences)
        settings = UserSettingsManager.update_user_settings(user.id, update_data)
        return {
            "code": 200,
            "status": "success",
            "data": settings.preferences,
            "message": "用户偏好更新成功"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户偏好失败: {str(e)}"
        )


@router.get("/theme")
async def get_user_theme(user=Depends(get_verified_user)):
    """
    获取用户主题设置
    
    Returns:
        dict: 主题设置
    """
    try:
        settings = UserSettingsManager.get_or_create_user_settings(user.id)
        return {
            "code": 200,
            "status": "success",
            "data": {"theme": settings.theme}
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取主题设置失败: {str(e)}"
        )


@router.put("/theme")
async def update_user_theme(
    request: ThemeUpdateRequest,
    user=Depends(get_verified_user)
):
    """
    更新用户主题设置
    
    Args:
        request: 主题更新请求
        
    Returns:
        dict: 更新结果
    """
    try:
        # 验证主题值
        if request.theme not in ["light", "dark", "system"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的主题值，必须是: light, dark, system"
            )
        
        success = UserSettingsManager.update_theme(user.id, request.theme)
        if success:
            return {
                "code": 200,
                "status": "success",
                "data": {"theme": request.theme},
                "message": "主题更新成功"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="主题更新失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新主题失败: {str(e)}"
        )


@router.put("/notifications/preference")
async def update_notification_preference(
    request: NotificationPreferenceRequest,
    user=Depends(get_verified_user)
):
    """
    更新通知偏好设置
    
    Args:
        request: 通知偏好更新请求
        
    Returns:
        dict: 更新结果
    """
    try:
        # 验证通知类型
        valid_types = ["solution", "mention", "system"]
        if request.type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的通知类型，必须是: {', '.join(valid_types)}"
            )
        
        success = UserSettingsManager.update_notification_preference(
            user.id, 
            request.type, 
            request.enabled
        )
        
        if success:
            return {
                "code": 200,
                "status": "success",
                "data": {
                    "type": request.type,
                    "enabled": request.enabled
                },
                "message": "通知偏好更新成功"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="通知偏好更新失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新通知偏好失败: {str(e)}"
        )


@router.delete("/settings")
async def delete_user_settings(user=Depends(get_verified_user)):
    """
    删除用户设置（重置为默认）
    
    Returns:
        dict: 删除结果
    """
    try:
        success = UserSettingsManager.delete_user_settings(user.id)
        if success:
            return {
                "code": 200,
                "status": "success",
                "message": "用户设置已重置为默认值"
            }
        else:
            return {
                "code": 200,
                "status": "success",
                "message": "用户设置已经是默认值"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除用户设置失败: {str(e)}"
        )
