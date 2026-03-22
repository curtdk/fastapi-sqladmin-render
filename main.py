"""
FastAPI + SQLAdmin 完整应用
包含：用户认证、注册、登录、JWT认证、SQLAdmin管理后台
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqladmin import Admin
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Optional, List
import os

from models import Base, User
from admin import setup_admin
from auth import (
    create_access_token, authenticate_user, create_user,
    get_current_user, get_current_active_user, get_current_admin_user,
    get_db, Token, UserCreate, UserResponse, UserInDB,
    verify_token, get_password_hash
)

# ==================== 应用配置 ====================

# 密钥配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-123456789")

# 创建 FastAPI 应用
app = FastAPI(
    title="FastAPI + SQLAdmin Demo",
    version="2.0.0",
    description="完整的用户认证系统 + 管理后台",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session中间件 - 用于SQLAdmin认证
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
)

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, echo=False)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 创建 SQLAdmin 管理界面
admin = Admin(
    app, 
    engine,
    title="贝壳后台管理系统",
    logo_url="https://f.tatagogo.com/favicon.ico"
)

# ==================== 首页 ====================

@app.get("/", tags=["首页"])
async def root():
    return {
        "message": "Welcome to FastAPI + SQLAdmin",
        "version": "2.0.0",
        "docs": "/docs",
        "admin": "/admin",
        "login": "/api/auth/login",
        "register": "/api/auth/register"
    }


@app.get("/health", tags=["健康检查"])
async def health():
    return {"status": "healthy", "database": "connected"}


# ==================== 认证API ====================

@app.post("/api/auth/register", response_model=UserResponse, tags=["认证"])
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    用户注册
    """
    # 检查邮箱是否已存在
    from auth import get_user_by_email
    existing_user = await get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 检查用户名是否已存在
    from auth import get_user_by_username
    existing_username = await get_user_by_username(db, user.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # 创建新用户
    db_user = await create_user(db, user)
    
    return db_user


@app.post("/api/auth/login", response_model=Token, tags=["认证"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录
    使用 OAuth2PasswordRequestForm (username/password)
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # 创建访问令牌
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "is_admin": user.is_admin}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        }
    }


@app.get("/api/auth/me", response_model=UserResponse, tags=["认证"])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    获取当前用户信息
    """
    return current_user


@app.post("/api/auth/admin-login", tags=["认证"])
async def admin_login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    管理员登录 - 登录后可访问/admin
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an admin user"
        )
    
    # 创建访问令牌
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "is_admin": user.is_admin}
    )
    
    # 将token保存到session (用于SQLAdmin)
    request.session.update({
        "token": access_token,
        "user_id": str(user.id),
        "username": user.username
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin
        },
        "message": "登录成功，请访问 /admin"
    }


@app.post("/api/auth/logout", tags=["认证"])
async def logout(current_user: User = Depends(get_current_active_user)):
    """
    用户登出
    """
    return {"message": "Successfully logged out"}


# ==================== 用户管理API (仅管理员) ====================

@app.get("/api/users", response_model=List[UserResponse], tags=["用户管理"])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取用户列表 (仅管理员)
    """
    from sqlalchemy import select
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return users


@app.get("/api/users/{user_id}", response_model=UserResponse, tags=["用户管理"])
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取指定用户 (仅管理员)
    """
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.delete("/api/users/{user_id}", tags=["用户管理"])
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    删除用户 (仅管理员)
    """
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted successfully"}


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup():
    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建默认管理员
    async with AsyncSessionLocal() as db:
        from auth import create_default_admin
        await create_default_admin(db)
    
    # 设置Admin面板
    setup_admin(admin)
    
    print("=" * 50)
    print("✅ 应用启动完成 - FastAPI + SQLAdmin v2.0")
    print("=" * 50)
    print(f"📊 数据库: {DATABASE_URL}")
    print("🔗 文档: http://localhost:10000/docs")
    print("👨‍💼 管理面板: http://localhost:10000/admin")
    print("🔐 默认管理员: admin / admin123")
    print("📝 注册API: POST /api/auth/register")
    print("🔑 登录API: POST /api/auth/login")
    print("=" * 50)


# 如果直接运行此文件
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
