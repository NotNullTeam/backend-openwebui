import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.internal.db import get_db
from open_webui.models.users import Users

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class UserPreferences(BaseModel):
    """用户偏好设置"""
    theme: str = Field(default="light", description="主题: light/dark/auto")
    language: str = Field(default="zh-CN", description="语言设置")
    timezone: str = Field(default="Asia/Shanghai", description="时区")
    notifications_enabled: bool = Field(default=True, description="是否启用通知")
    email_notifications: bool = Field(default=True, description="是否启用邮件通知")
    auto_save: bool = Field(default=True, description="自动保存")
    auto_save_interval: int = Field(default=30, ge=10, le=300, description="自动保存间隔(秒)")
    display_density: str = Field(default="comfortable", description="显示密度: compact/comfortable/spacious")
    sidebar_collapsed: bool = Field(default=False, description="侧边栏是否折叠")
    show_tips: bool = Field(default=True, description="显示提示")


class SearchPreferences(BaseModel):
    """搜索偏好设置"""
    default_search_scope: str = Field(default="all", description="默认搜索范围: all/cases/knowledge/files")
    search_history_enabled: bool = Field(default=True, description="启用搜索历史")
    max_search_history: int = Field(default=50, ge=0, le=200, description="最大搜索历史记录数")
    auto_suggest: bool = Field(default=True, description="自动建议")
    fuzzy_search: bool = Field(default=True, description="模糊搜索")
    highlight_results: bool = Field(default=True, description="高亮搜索结果")


class AIPreferences(BaseModel):
    """AI助手偏好设置"""
    default_model: Optional[str] = Field(default=None, description="默认AI模型")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(default=2048, ge=100, le=8192, description="最大令牌数")
    stream_response: bool = Field(default=True, description="流式响应")
    auto_title: bool = Field(default=True, description="自动生成标题")
    save_conversations: bool = Field(default=True, description="保存对话历史")


class PrivacySettings(BaseModel):
    """隐私设置"""
    data_collection: bool = Field(default=False, description="数据收集")
    usage_analytics: bool = Field(default=False, description="使用分析")
    share_feedback: bool = Field(default=True, description="分享反馈")
    public_profile: bool = Field(default=False, description="公开个人资料")


class UserSettings(BaseModel):
    """完整的用户设置"""
    user_id: str
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    search: SearchPreferences = Field(default_factory=SearchPreferences)
    ai: AIPreferences = Field(default_factory=AIPreferences)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="自定义设置")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UpdateSettingsRequest(BaseModel):
    """更新设置请求"""
    preferences: Optional[UserPreferences] = None
    search: Optional[SearchPreferences] = None
    ai: Optional[AIPreferences] = None
    privacy: Optional[PrivacySettings] = None
    custom_settings: Optional[Dict[str, Any]] = None


class CaseLayoutSettings(BaseModel):
    """案例布局设置"""
    layout_type: str = Field(default="grid", description="布局类型: grid/list/card")
    columns: int = Field(default=3, ge=1, le=6, description="列数")
    sort_by: str = Field(default="created_at", description="排序字段")
    sort_order: str = Field(default="desc", description="排序顺序: asc/desc")
    show_thumbnails: bool = Field(default=True, description="显示缩略图")
    show_summary: bool = Field(default=True, description="显示摘要")
    items_per_page: int = Field(default=20, ge=10, le=100, description="每页项目数")
    filters: Dict[str, Any] = Field(default_factory=dict, description="过滤器设置")


# 内存中的设置存储（生产环境应使用数据库）
_user_settings_store: Dict[str, UserSettings] = {}
_case_layouts_store: Dict[str, CaseLayoutSettings] = {}


@router.get("/", response_model=UserSettings)
async def get_user_settings(user=Depends(get_verified_user)):
    """
    获取当前用户的设置
    """
    user_id = user.id
    
    # 从存储中获取或创建默认设置
    if user_id not in _user_settings_store:
        _user_settings_store[user_id] = UserSettings(user_id=user_id)
    
    return _user_settings_store[user_id]


@router.put("/", response_model=UserSettings)
async def update_user_settings(
    request: UpdateSettingsRequest,
    user=Depends(get_verified_user)
):
    """
    更新当前用户的设置
    """
    user_id = user.id
    
    # 获取现有设置或创建新设置
    if user_id not in _user_settings_store:
        _user_settings_store[user_id] = UserSettings(user_id=user_id)
    
    settings = _user_settings_store[user_id]
    
    # 更新各个部分
    if request.preferences:
        settings.preferences = request.preferences
    if request.search:
        settings.search = request.search
    if request.ai:
        settings.ai = request.ai
    if request.privacy:
        settings.privacy = request.privacy
    if request.custom_settings:
        settings.custom_settings.update(request.custom_settings)
    
    settings.updated_at = datetime.utcnow()
    
    return settings


@router.delete("/")
async def reset_user_settings(user=Depends(get_verified_user)):
    """
    重置用户设置为默认值
    """
    user_id = user.id
    
    # 删除存储的设置，下次获取时会创建默认设置
    if user_id in _user_settings_store:
        del _user_settings_store[user_id]
    
    return {"message": "设置已重置为默认值"}


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(user=Depends(get_verified_user)):
    """
    获取用户偏好设置
    """
    settings = await get_user_settings(user)
    return settings.preferences


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    preferences: UserPreferences,
    user=Depends(get_verified_user)
):
    """
    更新用户偏好设置
    """
    user_id = user.id
    
    if user_id not in _user_settings_store:
        _user_settings_store[user_id] = UserSettings(user_id=user_id)
    
    _user_settings_store[user_id].preferences = preferences
    _user_settings_store[user_id].updated_at = datetime.utcnow()
    
    return preferences


@router.get("/search", response_model=SearchPreferences)
async def get_search_preferences(user=Depends(get_verified_user)):
    """
    获取搜索偏好设置
    """
    settings = await get_user_settings(user)
    return settings.search


@router.put("/search", response_model=SearchPreferences)
async def update_search_preferences(
    search: SearchPreferences,
    user=Depends(get_verified_user)
):
    """
    更新搜索偏好设置
    """
    user_id = user.id
    
    if user_id not in _user_settings_store:
        _user_settings_store[user_id] = UserSettings(user_id=user_id)
    
    _user_settings_store[user_id].search = search
    _user_settings_store[user_id].updated_at = datetime.utcnow()
    
    return search


@router.get("/ai", response_model=AIPreferences)
async def get_ai_preferences(user=Depends(get_verified_user)):
    """
    获取AI助手偏好设置
    """
    settings = await get_user_settings(user)
    return settings.ai


@router.put("/ai", response_model=AIPreferences)
async def update_ai_preferences(
    ai: AIPreferences,
    user=Depends(get_verified_user)
):
    """
    更新AI助手偏好设置
    """
    user_id = user.id
    
    if user_id not in _user_settings_store:
        _user_settings_store[user_id] = UserSettings(user_id=user_id)
    
    _user_settings_store[user_id].ai = ai
    _user_settings_store[user_id].updated_at = datetime.utcnow()
    
    return ai


@router.get("/privacy", response_model=PrivacySettings)
async def get_privacy_settings(user=Depends(get_verified_user)):
    """
    获取隐私设置
    """
    settings = await get_user_settings(user)
    return settings.privacy


@router.put("/privacy", response_model=PrivacySettings)
async def update_privacy_settings(
    privacy: PrivacySettings,
    user=Depends(get_verified_user)
):
    """
    更新隐私设置
    """
    user_id = user.id
    
    if user_id not in _user_settings_store:
        _user_settings_store[user_id] = UserSettings(user_id=user_id)
    
    _user_settings_store[user_id].privacy = privacy
    _user_settings_store[user_id].updated_at = datetime.utcnow()
    
    return privacy


# 案例布局设置
@router.get("/case-layout", response_model=CaseLayoutSettings)
async def get_case_layout(user=Depends(get_verified_user)):
    """
    获取案例布局设置
    """
    user_id = user.id
    
    if user_id not in _case_layouts_store:
        _case_layouts_store[user_id] = CaseLayoutSettings()
    
    return _case_layouts_store[user_id]


@router.put("/case-layout", response_model=CaseLayoutSettings)
async def save_case_layout(
    layout: CaseLayoutSettings,
    user=Depends(get_verified_user)
):
    """
    保存案例布局设置
    """
    user_id = user.id
    _case_layouts_store[user_id] = layout
    
    return layout


@router.delete("/case-layout")
async def reset_case_layout(user=Depends(get_verified_user)):
    """
    重置案例布局为默认设置
    """
    user_id = user.id
    
    if user_id in _case_layouts_store:
        del _case_layouts_store[user_id]
    
    return {"message": "案例布局已重置为默认设置"}


# 导出/导入设置
@router.get("/export")
async def export_settings(user=Depends(get_verified_user)):
    """
    导出用户所有设置
    """
    user_id = user.id
    
    settings = await get_user_settings(user)
    case_layout = await get_case_layout(user)
    
    export_data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "user_settings": settings.model_dump(),
        "case_layout": case_layout.model_dump()
    }
    
    return export_data


@router.post("/import")
async def import_settings(
    import_data: Dict[str, Any],
    user=Depends(get_verified_user)
):
    """
    导入用户设置
    """
    user_id = user.id
    
    try:
        # 验证版本
        if import_data.get("version") != "1.0":
            raise HTTPException(
                status_code=400,
                detail="不支持的设置版本"
            )
        
        # 导入用户设置
        if "user_settings" in import_data:
            settings_data = import_data["user_settings"]
            settings = UserSettings(**settings_data)
            settings.user_id = user_id  # 使用当前用户ID
            settings.updated_at = datetime.utcnow()
            _user_settings_store[user_id] = settings
        
        # 导入案例布局
        if "case_layout" in import_data:
            layout_data = import_data["case_layout"]
            layout = CaseLayoutSettings(**layout_data)
            _case_layouts_store[user_id] = layout
        
        return {"message": "设置导入成功"}
        
    except Exception as e:
        log.error(f"Failed to import settings: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"设置导入失败: {str(e)}"
        )
