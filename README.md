# FastAPI + SQLAdmin Demo

一个完整的 FastAPI 应用，集成 SQLAdmin 管理界面，部署到 Render。

## 功能特性

- ✅ **FastAPI** - 现代、高性能 Web 框架
- ✅ **SQLAdmin** - 强大的 SQLAlchemy 管理界面
- ✅ **SQLAlchemy 2.0** - 异步 ORM
- ✅ **SQLite 数据库** - 轻量级数据库（可替换为 PostgreSQL）
- ✅ **完整 CRUD** - 用户、产品、订单、文章管理
- ✅ **身份验证** - 简单的 Admin 登录
- ✅ **响应式设计** - 适配移动端

## 快速开始

### 1. 本地运行

```bash
# 克隆项目
git clone <repository-url>
cd fastapi-sqladmin-render

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行应用
uvicorn main:app --host 0.0.0.0 --port 10000 --reload
```

### 2. 访问地址

- **应用首页**: http://localhost:10000
- **API 文档**: http://localhost:10000/docs
- **管理面板**: http://localhost:10000/admin
- **健康检查**: http://localhost:10000/health

### 3. 管理员登录

- **用户名**: `admin`
- **密码**: `admin`

## 项目结构

```
fastapi-sqladmin-render/
├── main.py              # FastAPI 主应用
├── models.py            # SQLAlchemy 数据模型
├── admin.py             # SQLAdmin 配置
├── requirements.txt     # Python 依赖
├── README.md           # 项目说明
└── .gitignore          # Git 忽略文件
```

## 数据模型

1. **User** - 用户管理
2. **Product** - 产品管理
3. **Order** - 订单管理
4. **OrderItem** - 订单项管理
5. **Post** - 博客文章管理

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 欢迎页面 |
| `/health` | GET | 健康检查 |
| `/test-db` | GET | 数据库连接测试 |
| `/docs` | GET | Swagger UI 文档 |
| `/openapi.json` | GET | OpenAPI 规范 |

## 部署到 Render

### 自动部署（推荐）

本项目已配置为自动部署到 Render：

1. **推送代码到 GitHub**
2. **连接 Render** 到 GitHub 仓库
3. **自动构建和部署**

### 手动部署

1. 在 Render 创建新的 Web Service
2. 选择你的 GitHub 仓库
3. 配置构建命令：
   ```
   pip install -r requirements.txt
   ```
4. 配置启动命令：
   ```
   uvicorn main:app --host 0.0.0.0 --port 10000
   ```
5. 设置环境变量（可选）：
   - `DATABASE_URL`: 数据库连接字符串

## 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./app.db` | 数据库连接字符串 |
| `PORT` | `10000` | 应用端口 |

## 开发

### 添加新模型

1. 在 `models.py` 中定义新模型
2. 在 `admin.py` 中创建对应的 Admin 类
3. 在 `setup_admin()` 函数中添加视图

### 更换数据库

修改 `DATABASE_URL` 环境变量：

```python
# PostgreSQL 示例
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

# MySQL 示例  
DATABASE_URL = "mysql+asyncmy://user:password@localhost/dbname"
```

## 许可证

MIT