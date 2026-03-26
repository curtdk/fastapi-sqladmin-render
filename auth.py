"""
安全认证模块
包含：JWT认证、RBAC权限、CORS、速率限制、域名限制、日志
"""
import os
import re
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Callable
from functools import wraps

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from passlib.context import CryptContext
from jose import JWTError, jwt, ExpiredSignatureError
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

# ==================== 配置 ====================

SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-123456789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 默认24小时(1440分钟)
REFRESH_TOKEN_EXPIRE_DAYS = 7

# CORS白名单（允许的域名）
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://beike.tatagogo.com,http://api.beike.tatagogo.com").split(",")

# 允许访问的域名（类似 Django ALLOWED_HOSTS）
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "beike.tatagogo.com,api.beike.tatagogo.com").split(",")

# 速率限制
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# 速率限制器
limiter = Limiter(key_func=get_remote_address)

# 日志配置
logger = logging.getLogger("auth")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)


# ==================== Pydantic 模型 ====================

from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    is_admin: bool = False
    is_superuser: bool = False
    jti: Optional[str] = None  # JWT ID


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    is_superuser: bool
    created_at: datetime
    roles: Optional[List[dict]] = []
    
    class Config:
        from_attributes = True


class LoginLog(BaseModel):
    """登录日志摘要"""
    last_login: Optional[datetime] = None
    login_count: int = 0


# ==================== ALLOWED_HOSTS 中间件 ====================

class HostCheckMiddleware(BaseHTTPMiddleware):
    """
    类似 Django ALLOWED_HOSTS 的域名检查中间件
    所有非白名单域名的请求返回 400
    """
    
    async def dispatch(self, request: Request, call_next):
        # WebSocket 和静态资源不做检查
        if request.url.path in ["/docs", "/redoc", "/openapi.json"] and os.getenv("ENVIRONMENT") == "production":
            return JSONResponse(
                status_code=404,
                content={"detail": "API docs disabled in production"}
            )
        
        host = request.headers.get("host", "").split(":")[0]
        
        # 检查 host 是否在白名单
        if host not in ALLOWED_HOSTS and os.getenv("ENVIRONMENT") == "production":
            logger.warning(f"Blocked request from disallowed host: {host}")
            return JSONResponse(
                status_code=400,
                content={"detail": f"Host '{host}' is not allowed. Please access via allowed domains: {', '.join(ALLOWED_HOSTS)}"}
            )
        
        response = await call_next(request)
        return response


# ==================== 操作日志中间件 ====================

async def log_operation(
    db: AsyncSession,
    user_id: int,
    username: str,
    action: str,
    model: str = None,
    object_id: int = None,
    description: str = None,
    request: Request = None,
    status: str = "success",
    details: dict = None
):
    """记录操作日志"""
    from models import OperationLog
    
    log = OperationLog(
        user_id=user_id,
        username=username,
        action=action,
        model=model,
        object_id=str(object_id) if object_id else None,
        description=description,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        status=status,
        details=json.dumps(details) if details else None
    )
    db.add(log)
    await db.commit()


# ==================== 数据库会话 ====================

from models import Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# ==================== 密码处理 ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ==================== JWT 处理 ====================

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    refresh: bool = False
) -> tuple[str, str]:
    """
    创建访问令牌或刷新令牌
    返回 (token, jti)
    """
    jti = str(uuid.uuid4())
    to_encode = data.copy()
    to_encode.update({
        "jti": jti,
        "type": "refresh" if refresh else "access"
    })
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        if refresh:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return token, jti


def decode_token(token: str) -> Optional[TokenData]:
    """解码并验证 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
        username: str = payload.get("username")
        is_admin: bool = payload.get("is_admin", False)
        is_superuser: bool = payload.get("is_superuser", False)
        jti: str = payload.get("jti")
        
        if user_id is None:
            return None
        
        return TokenData(
            user_id=user_id,
            username=username,
            is_admin=is_admin,
            is_superuser=is_superuser,
            jti=jti
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        return None


async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    """检查 token 是否在黑名单"""
    from models import TokenBlacklist
    result = await db.execute(
        select(TokenBlacklist).where(TokenBlacklist.token_jti == jti)
    )
    return result.scalars().first() is not None


async def add_token_to_blacklist(db: AsyncSession, jti: str, user_id: int, expires_at: datetime):
    """将 token 加入黑名单"""
    from models import TokenBlacklist
    blacklist_entry = TokenBlacklist(
        token_jti=jti,
        user_id=user_id,
        expires_at=expires_at
    )
    db.add(blacklist_entry)
    await db.commit()


# ==================== 数据库操作 ====================

async def get_user_by_id(db: AsyncSession, user_id: int):
    from models import User
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def get_user_by_username(db: AsyncSession, username: str):
    from models import User
    result = await db.execute(select(User).where(User.username == username))
    return result.scalars().first()


async def get_user_by_email(db: AsyncSession, email: str):
    from models import User
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def authenticate_user(db: AsyncSession, username: str, password: str):
    from models import User
    user = await get_user_by_username(db, username)
    if not user:
        user = await get_user_by_email(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(db: AsyncSession, user_data: UserCreate, is_admin: bool = False) -> "User":
    from models import User, UserRole
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_admin=is_admin,
        is_active=True
    )
    db.add(user)
    await db.flush()
    
    # 绑定角色
    if user_data.role_ids:
        for role_id in user_data.role_ids:
            db.add(UserRole(user_id=user.id, role_id=role_id))
    
    await db.commit()
    await db.refresh(user)
    return user


# ==================== 权限检查 ====================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """获取当前登录用户"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查是否在黑名单
    if await is_token_blacklisted(db, token_data.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_id(db, token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(current_user = Depends(get_current_user)):
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def require_admin(current_user = Depends(get_current_active_user)):
    """必须是管理员"""
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_permission(perm_code: str):
    """装饰器：检查指定权限"""
    async def permission_checker(current_user = Depends(get_current_active_user)):
        if current_user.is_admin or current_user.is_superuser:
            return current_user
        
        # 检查用户权限
        for role in current_user.roles:
            for perm in role.permissions:
                if perm.code == perm_code:
                    return current_user
        
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {perm_code}"
        )
    return permission_checker


# ==================== 依赖注入：获取用户菜单 ====================

async def get_user_menus(db: AsyncSession, current_user) -> List[dict]:
    """
    根据用户角色生成菜单
    每个菜单项格式：{name, icon, url, children: []}
    """
    from models import Permission
    
    if current_user.is_admin or current_user.is_superuser:
        # 管理员看到全部菜单
        return [
            {"name": "仪表盘", "icon": "fa-home", "url": "/admin"},
            {"name": "用户", "icon": "fa-user", "url": "/admin/users", "model": "User"},
            {"name": "产品", "icon": "fa-box", "url": "/admin/products", "model": "Product"},
            {"name": "订单", "icon": "fa-receipt", "url": "/admin/orders", "model": "Order"},
            {"name": "文章", "icon": "fa-newspaper", "url": "/admin/posts", "model": "Post"},
            {"name": "角色", "icon": "fa-shield", "url": "/admin/roles", "model": "Role"},
            {"name": "权限", "icon": "fa-key", "url": "/admin/permissions", "model": "Permission"},
            {"name": "日志", "icon": "fa-history", "url": "/admin/logs", "model": "OperationLog"},
        ]
    
    # 普通用户：根据权限生成菜单
    menu_map = {
        "User": {"name": "用户", "icon": "fa-user", "url": "/admin/users"},
        "Product": {"name": "产品", "icon": "fa-box", "url": "/admin/products"},
        "Order": {"name": "订单", "icon": "fa-receipt", "url": "/admin/orders"},
        "Post": {"name": "文章", "icon": "fa-newspaper", "url": "/admin/posts"},
        "Role": {"name": "角色", "icon": "fa-shield", "url": "/admin/roles"},
        "Permission": {"name": "权限", "icon": "fa-key", "url": "/admin/permissions"},
        "OperationLog": {"name": "日志", "icon": "fa-history", "url": "/admin/logs"},
    }
    
    allowed_models = set()
    for role in current_user.roles:
        for perm in role.permissions:
            if perm.action == "view":
                allowed_models.add(perm.model)
    
    menus = []
    for model, info in menu_map.items():
        if model in allowed_models:
            menus.append(info)
    
    return menus


# ==================== 创建默认数据 ====================

async def init_rbac_default_data(db: AsyncSession):
    """
    初始化 RBAC 默认数据：
    - 默认管理员 admin / admin123
    - 默认角色：超级管理员、内容管理员、运营
    - 默认权限
    """
    from models import User, Role, Permission, UserRole
    
    # 创建默认权限
    all_permissions = [
        # 用户权限
        ("查看用户", "user.view", "User", "view"),
        ("新增用户", "user.add", "User", "add"),
        ("编辑用户", "user.edit", "User", "edit"),
        ("删除用户", "user.delete", "User", "delete"),
        # 产品权限
        ("查看产品", "product.view", "Product", "view"),
        ("新增产品", "product.add", "Product", "add"),
        ("编辑产品", "product.edit", "Product", "edit"),
        ("删除产品", "product.delete", "Product", "delete"),
        # 订单权限
        ("查看订单", "order.view", "Order", "view"),
        ("新增订单", "order.add", "Order", "add"),
        ("编辑订单", "order.edit", "Order", "edit"),
        ("删除订单", "order.delete", "Order", "delete"),
        # 文章权限
        ("查看文章", "post.view", "Post", "view"),
        ("新增文章", "post.add", "Post", "add"),
        ("编辑文章", "post.edit", "Post", "edit"),
        ("删除文章", "post.delete", "Post", "delete"),
        # 角色权限
        ("查看角色", "role.view", "Role", "view"),
        ("新增角色", "role.add", "Role", "add"),
        ("编辑角色", "role.edit", "Role", "edit"),
        ("删除角色", "role.delete", "Role", "delete"),
        # 权限权限
        ("查看权限", "permission.view", "Permission", "view"),
        # 日志权限
        ("查看日志", "log.view", "OperationLog", "view"),
    ]
    
    perm_map = {}
    for name, code, model, action in all_permissions:
        result = await db.execute(select(Permission).where(Permission.code == code))
        existing = result.scalars().first()
        if not existing:
            perm = Permission(name=name, code=code, model=model, action=action)
            db.add(perm)
            await db.flush()
            perm_map[code] = perm
        else:
            perm_map[code] = existing
    
    # 创建默认角色
    roles_data = {
        "超级管理员": {
            "code": "super_admin",
            "description": "拥有所有权限",
            "permissions": [p for p in perm_map.values()]
        },
        "内容管理员": {
            "code": "content_admin",
            "description": "管理产品和文章",
            "permissions": [perm_map[p] for p in [
                "product.view", "product.add", "product.edit", "product.delete",
                "post.view", "post.add", "post.edit", "post.delete",
            ] if p in perm_map]
        },
        "运营": {
            "code": "operator",
            "description": "查看和编辑订单",
            "permissions": [perm_map[p] for p in [
                "order.view", "order.add", "order.edit",
                "product.view",
            ] if p in perm_map]
        },
    }
    
    role_map = {}
    for name, data in roles_data.items():
        result = await db.execute(select(Role).where(Role.code == data["code"]))
        existing = result.scalars().first()
        if not existing:
            role = Role(name=name, code=data["code"], description=data["description"], is_active=True)
            role.permissions = data["permissions"]
            db.add(role)
            await db.flush()
            role_map[data["code"]] = role
            # 刷新加载 permissions 关系
            await db.refresh(role, ["permissions"])
        else:
            # 如果存在，不更新权限，避免 greenlet 问题
            role_map[data["code"]] = existing
    
    # 创建默认管理员
    admin = await get_user_by_username(db, "admin")
    if not admin:
        admin = User(
            email="admin@example.com",
            username="admin",
            full_name="系统管理员",
            hashed_password=get_password_hash("admin123"),
            is_admin=True,
            is_superuser=True,
            is_active=True
        )
        db.add(admin)
        await db.flush()
        
        # 绑定超级管理员角色
        if "super_admin" in role_map:
            db.add(UserRole(user_id=admin.id, role_id=role_map["super_admin"].id))
        
        await db.commit()
        logger.info("✅ 默认管理员已创建: admin / admin123 (super_admin role)")
    else:
        # 确保admin有超级管理员权限
        if not admin.is_admin:
            admin.is_admin = True
        if not admin.is_superuser:
            admin.is_superuser = True
        await db.commit()
        logger.info("✅ 管理员权限已确认")
    
    logger.info("✅ RBAC 默认数据初始化完成")
