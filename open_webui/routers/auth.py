"""
认证路由器 - 兼容旧系统API路径
提供与原backend系统兼容的认证接口
"""

import logging
import time
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from open_webui.models.auths import (
    Auths,
    SignupForm,
    SigninForm,
    UpdatePasswordForm,
)
from open_webui.models.users import Users
from open_webui.constants import ERROR_MESSAGES
from open_webui.utils.auth import (
    create_token,
    decode_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from open_webui.utils.misc import parse_duration, validate_email_format
from open_webui.env import WEBUI_AUTH_COOKIE_SAME_SITE, WEBUI_AUTH_COOKIE_SECURE

router = APIRouter(prefix="/auth", tags=["Auth"])

log = logging.getLogger(__name__)


############################
# Request/Response Models
############################

class RegisterRequest(BaseModel):
    """用户注册请求"""
    email: str
    password: str
    name: str
    profile_image_url: Optional[str] = "/user.png"


class RefreshRequest(BaseModel):
    """Token刷新请求"""
    refresh_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """密码修改请求"""
    old_password: str
    new_password: str


class AuthResponse(BaseModel):
    """认证响应"""
    token: str
    token_type: str = "Bearer"
    expires_at: Optional[int] = None
    user: dict


class LoginRequest(BaseModel):
    """用户登录请求"""
    email: str
    password: str


############################
# POST /auth/login - 用户登录
############################

@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    response: Response,
    form_data: LoginRequest
):
    """
    用户登录接口
    兼容旧系统的 /api/v1/auth/login
    """
    # 验证邮箱格式
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )
    
    # 认证用户
    user = Auths.authenticate_user(form_data.email.lower(), form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.INVALID_CREDENTIALS
        )
    
    # 生成token
    expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())
    
    token = create_token(
        data={"id": user.id},
        expires_delta=expires_delta,
    )
    
    # 设置cookie
    response.set_cookie(
        key="token",
        value=token,
        expires=(
            datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
            if expires_at
            else None
        ),
        httponly=True,
        samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
        secure=WEBUI_AUTH_COOKIE_SECURE,
    )
    
    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "profile_image_url": user.profile_image_url,
        }
    }


############################
# POST /auth/register - 用户注册
############################

@router.post("/register", response_model=AuthResponse)
async def register(
    request: Request,
    response: Response,
    form_data: RegisterRequest
):
    """
    用户注册接口
    兼容旧系统的 /api/v1/auth/register
    """
    # 检查是否允许注册
    if not request.app.state.config.ENABLE_SIGNUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User registration is disabled"
        )
    
    # 验证邮箱格式
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )
    
    # 检查邮箱是否已存在
    if Users.get_user_by_email(form_data.email.lower()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.EMAIL_TAKEN
        )
    
    try:
        # 确定用户角色
        has_users = Users.has_users()
        role = "admin" if not has_users else request.app.state.config.DEFAULT_USER_ROLE
        
        # 密码长度检查
        if len(form_data.password.encode("utf-8")) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.PASSWORD_TOO_LONG
            )
        
        # 创建用户
        hashed = get_password_hash(form_data.password)
        user = Auths.insert_new_auth(
            email=form_data.email.lower(),
            password=hashed,
            name=form_data.name,
            profile_image_url=form_data.profile_image_url,
            role=role
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ERROR_MESSAGES.CREATE_USER_ERROR
            )
        
        # 生成token
        expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
        expires_at = None
        if expires_delta:
            expires_at = int(time.time()) + int(expires_delta.total_seconds())
        
        token = create_token(
            data={"id": user.id},
            expires_delta=expires_delta,
        )
        
        # 设置cookie
        response.set_cookie(
            key="token",
            value=token,
            expires=(
                datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                if expires_at
                else None
            ),
            httponly=True,
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )
        
        return {
            "token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "profile_image_url": user.profile_image_url,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during registration"
        )


############################
# POST /auth/refresh - Token刷新
############################

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    response: Response,
    form_data: RefreshRequest,
    current_user=Depends(get_current_user)
):
    """
    Token刷新接口
    兼容旧系统的 /api/v1/auth/refresh
    """
    try:
        # 生成新token
        expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
        expires_at = None
        if expires_delta:
            expires_at = int(time.time()) + int(expires_delta.total_seconds())
        
        new_token = create_token(
            data={"id": current_user.id},
            expires_delta=expires_delta,
        )
        
        # 更新cookie
        response.set_cookie(
            key="token",
            value=new_token,
            expires=(
                datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                if expires_at
                else None
            ),
            httponly=True,
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )
        
        return {
            "token": new_token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "role": current_user.role,
                "profile_image_url": current_user.profile_image_url,
            }
        }
        
    except Exception as e:
        log.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )


############################
# POST /auth/logout - 用户登出
############################

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user)
):
    """
    用户登出接口
    兼容旧系统的 /api/v1/auth/logout
    """
    # 清除cookie
    response.delete_cookie("token")
    response.delete_cookie("oui-session")
    
    return {
        "status": True,
        "message": "Successfully logged out"
    }


############################
# POST /auth/change-password - 修改密码
############################

@router.post("/change-password", response_model=dict)
async def change_password(
    request: Request,
    form_data: ChangePasswordRequest,
    current_user=Depends(get_current_user)
):
    """
    密码修改接口
    兼容旧系统的 /api/v1/auth/change-password
    """
    # 验证旧密码
    user = Auths.authenticate_user(current_user.email, form_data.old_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password"
        )
    
    # 密码长度检查
    if len(form_data.new_password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.PASSWORD_TOO_LONG
        )
    
    # 更新密码
    hashed = get_password_hash(form_data.new_password)
    success = Auths.update_user_password_by_id(user.id, hashed)
    
    if success:
        return {
            "status": True,
            "message": "Password updated successfully"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
