"""
FastAPI + SQLAdmin RBAC 完整应用
包含：JWT认证、RBAC权限、CORS、速率限制、域名白名单、操作日志
"""
import os

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import Base
from admin import setup_admin
from auth import (
    get_db, get_current_user, get_current_active_user, require_admin,
    create_access_token, authenticate_user, get_user_menus,
    init_rbac_default_data, limiter, ALLOWED_HOSTS, CORS_ORIGINS,
    verify_password, get_password_hash, log_operation, create_user,
    UserCreate, UserUpdate, UserResponse, Token,
    AsyncSessionLocal
)
from auth import HostCheckMiddleware


# ==================== 全局变量 ====================

app = FastAPI(
    title="贝壳后台管理系统",
    version="3.0.0",
    description="FastAPI + SQLAdmin + RBAC",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None,
)

# 速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Session 中间件（SQLAdmin 需要）
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-123456789")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 域名检查中间件（生产环境）
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HostCheckMiddleware)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Authorization"],
)

# Admin 对象（startup 时初始化）
admin = None


# ==================== 认证 API ====================

@app.post("/api/auth/login", response_model=Token, tags=["认证"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="账户已被禁用")
    if not user.is_admin and not user.is_superuser:
        raise HTTPException(status_code=403, detail="非管理员账户无法登录后台")

    access_token, access_jti = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_superuser": user.is_superuser
        }
    )
    refresh_token, refresh_jti = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "is_admin": user.is_admin,
            "is_superuser": user.is_superuser
        },
        refresh=True
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "is_superuser": user.is_superuser
        }
    }


@app.post("/api/auth/logout", tags=["认证"])
async def logout(
    request: Request,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """用户登出"""
    await log_operation(
        db=db,
        user_id=current_user.id,
        username=current_user.username,
        action="LOGOUT",
        description="用户登出",
        request=request,
        status="success"
    )
    return {"message": "登出成功"}


@app.post("/api/auth/register", response_model=UserResponse, tags=["认证"])
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """注册用户（仅管理员）"""
    from auth import get_user_by_email, get_user_by_username
    if await get_user_by_email(db, user_data.email):
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    if await get_user_by_username(db, user_data.username):
        raise HTTPException(status_code=400, detail="用户名已被使用")
    user = await create_user(db, user_data)
    await log_operation(
        db=db, user_id=current_user.id, username=current_user.username,
        action="CREATE", model="User", object_id=user.id,
        description=f"新增用户 {user.username}", request=None, status="success"
    )
    return user


@app.get("/api/auth/me", tags=["认证"])
async def read_me(current_user = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at,
        "roles": []
    }


@app.get("/api/auth/menus", tags=["认证"])
async def get_menus(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的菜单"""
    return await get_user_menus(db, current_user)


# ==================== 用户管理 API ====================

@app.get("/api/users", tags=["用户管理"])
async def list_users(
    skip: int = 0, limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """获取用户列表（仅管理员）"""
    from sqlalchemy import select
    from models import User
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email,
            "full_name": u.full_name, "is_active": u.is_active,
            "is_admin": u.is_admin, "is_superuser": u.is_superuser,
            "created_at": u.created_at
        }
        for u in users
    ]


@app.put("/api/users/{user_id}", tags=["用户管理"])
async def update_user(
    user_id: int, data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """更新用户（仅管理员）"""
    from sqlalchemy import select
    from models import User, UserRole
    from auth import get_user_by_email, get_user_by_username

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if data.email and data.email != user.email:
        if await get_user_by_email(db, data.email):
            raise HTTPException(status_code=400, detail="邮箱已被使用")
        user.email = data.email
    if data.username and data.username != user.username:
        if await get_user_by_username(db, data.username):
            raise HTTPException(status_code=400, detail="用户名已被使用")
        user.username = data.username
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.password:
        user.hashed_password = verify_password(data.password) if not data.password.startswith("$") else data.password
        from auth import get_password_hash
        user.hashed_password = get_password_hash(data.password)
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role_ids is not None:
        await db.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user_id)
        )
        for role_id in data.role_ids:
            db.add(UserRole(user_id=user.id, role_id=role_id))

    await db.commit()
    await log_operation(
        db=db, user_id=current_user.id, username=current_user.username,
        action="UPDATE", model="User", object_id=user_id,
        description=f"更新用户 {user.username}", status="success"
    )
    return {"id": user.id, "username": user.username, "message": "更新成功"}


@app.delete("/api/users/{user_id}", tags=["用户管理"])
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_admin)
):
    """删除用户（仅管理员）"""
    from sqlalchemy import select
    from models import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    username = user.username
    await db.delete(user)
    await db.commit()
    await log_operation(
        db=db, user_id=current_user.id, username=current_user.username,
        action="DELETE", model="User", object_id=user_id,
        description=f"删除用户 {username}", status="success"
    )
    return {"message": "用户已删除"}


# ==================== 健康检查 ====================

@app.get("/health", tags=["健康检查"])
async def health():
    return {"status": "healthy", "version": "3.0.0", "rbac": "enabled"}


@app.get("/", tags=["首页"])
async def root():
    return {
        "message": "贝壳后台管理系统 v3.0",
        "version": "3.0.0",
        "docs": "/docs" if os.getenv("ENVIRONMENT") != "production" else "disabled",
        "admin": "/admin",
        "rbac": True
    }


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup():
    global admin
    from sqladmin import Admin

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

    # 创建异步引擎和会话工厂
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 初始化 RBAC 默认数据
    async with async_session_maker() as db:
        await init_rbac_default_data(db)

    # 创建 Admin（正确传递 engine 和 session_maker）
    admin = Admin(
        app,
        engine=engine,
        session_maker=async_session_maker,
        title="贝壳后台管理系统",
        logo_url="https://beike.tatagogo.com/favicon.ico",
    )

    # 设置 Admin 视图和认证
    setup_admin(admin)

    print("=" * 50)
    print("✅ 贝壳系统 v3.0 启动完成")
    print("=" * 50)
    print(f"📊 数据库: {DATABASE_URL}")
    print(f"🔐 文档: {'http://api.beike.tatagogo.com/docs' if os.getenv('ENVIRONMENT') != 'production' else 'disabled'}")
    print(f"👨‍💼 管理后台: http://api.beike.tatagogo.com/admin")
    print(f"🔑 默认管理员: admin / admin123")
    print(f"🌐 允许域名: {', '.join(ALLOWED_HOSTS)}")
    print(f"🔒 CORS白名单: {', '.join(CORS_ORIGINS)}")
    print("=" * 50)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
