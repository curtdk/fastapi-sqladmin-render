from fastapi import FastAPI
from sqladmin import Admin
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# 创建 FastAPI 应用
app = FastAPI(title="FastAPI + SQLAdmin Demo", version="1.0.0")

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, echo=True)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 创建 SQLAdmin 管理界面
admin = Admin(app, engine)

# 首页路由
@app.get("/")
async def root():
    return {
        "message": "Welcome to FastAPI + SQLAdmin Demo",
        "docs": "/docs",
        "admin": "/admin",
        "openapi": "/openapi.json"
    }

# 健康检查
@app.get("/health")
async def health():
    return {"status": "healthy", "database": "connected"}

# 数据库连接测试
@app.get("/test-db")
async def test_db():
    try:
        async with AsyncSessionLocal() as session:
            # 执行简单查询测试数据库连接
            result = await session.execute("SELECT 1")
            return {"database": "connected", "result": result.scalar()}
    except Exception as e:
        return {"database": "error", "error": str(e)}

# 导入模型和Admin配置（避免循环导入）
from models import Base
from admin import setup_admin

# 在应用启动时创建数据库表
@app.on_event("startup")
async def startup():
    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 设置Admin面板
    setup_admin(admin)
    
    print("✅ 应用启动完成")
    print(f"📊 数据库: {DATABASE_URL}")
    print("🔗 文档: http://localhost:10000/docs")
    print("👨‍💼 管理面板: http://localhost:10000/admin")