"""
SQLAdmin认证集成
实现基于JWT的真实登录认证
"""
import os
from sqladmin import ModelView, Admin
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import User, Product, Order, OrderItem, Post
from auth import verify_token, AsyncSessionLocal, get_user_by_id


# ==================== JWT认证后端 ====================

class JWTAuthenticationBackend(AuthenticationBackend):
    """
    JWT认证后端
    访问/admin需要先登录
    """
    
    async def login(self, request: Request) -> bool:
        """处理登录 - 验证用户名密码并创建session"""
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            return False
        
        if not username or not password:
            return False
        
        # 验证用户名密码
        async with AsyncSessionLocal() as db:
            from auth import authenticate_user, create_access_token
            
            user = await authenticate_user(db, username, password)
            if not user or not user.is_active or not user.is_admin:
                return False
            
            # 创建token
            token = create_access_token(
                data={"sub": str(user.id), "username": user.username, "is_admin": user.is_admin}
            )
            
            # 保存到session
            request.session.update({
                "token": token, 
                "user_id": str(user.id),
                "username": user.username
            })
        
        return True

    async def logout(self, request: Request) -> bool:
        """处理登出"""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """验证请求"""
        # 检查session中是否有token
        token = request.session.get("token")
        
        if not token:
            return False
        
        # 验证token
        token_data = await verify_token(token)
        if not token_data:
            return False
        
        # 验证用户
        async with AsyncSessionLocal() as db:
            user = await get_user_by_id(db, token_data.user_id)
            if not user or not user.is_active or not user.is_admin:
                return False
        
        return True


# ==================== Admin视图 ====================

class UserAdmin(ModelView, model=User):
    """用户管理视图"""
    name = "用户"
    name_plural = "用户管理"
    icon = "fa-solid fa-user"
    
    # 列表显示列
    column_list = [
        User.id, User.username, User.email, User.full_name, 
        User.is_active, User.is_admin, User.is_superuser, User.created_at
    ]
    
    # 可搜索列
    column_searchable_list = [User.username, User.email, User.full_name]
    
    # 可排序列
    column_sortable_list = [User.id, User.created_at, User.username, User.email]
    column_default_sort = [(User.id, True)]
    
    # 表单列
    form_columns = [
        User.username, User.email, User.full_name, 
        User.hashed_password, User.is_active, User.is_admin, User.is_superuser
    ]
    
    # 详情页显示
    column_details_list = [
        User.id, User.username, User.email, User.full_name,
        User.is_active, User.is_admin, User.is_superuser,
        User.created_at, User.updated_at
    ]
    
    # 页面大小
    page_size = 20
    page_size_options = [10, 20, 50, 100]
    
    # 密码表单配置 - 不在列表中显示密码
    form_widget_args = {
        User.hashed_password: {"type": "password", "placeholder": "留空则不修改密码"}
    }
    
    async def insert_model(self, request: Request, data: dict):
        """插入用户时处理密码"""
        from auth import get_password_hash
        if data.get("hashed_password"):
            data["hashed_password"] = get_password_hash(data["hashed_password"])
        return await super().insert_model(request, data)
    
    async def update_model(self, request: Request, pk: dict, data: dict):
        """更新用户时处理密码"""
        from auth import get_password_hash
        if data.get("hashed_password"):
            data["hashed_password"] = get_password_hash(data["hashed_password"])
        return await super().update_model(request, pk, data)


class ProductAdmin(ModelView, model=Product):
    """产品管理视图"""
    name = "产品"
    name_plural = "产品管理"
    icon = "fa-solid fa-box"
    
    column_list = [
        Product.id, Product.name, Product.price, Product.stock, 
        Product.category, Product.is_available, Product.owner_id, Product.created_at
    ]
    column_searchable_list = [Product.name, Product.category]
    column_sortable_list = [Product.id, Product.price, Product.stock, Product.created_at]
    column_default_sort = [(Product.id, True)]
    
    form_columns = [
        Product.name, Product.description, Product.price, Product.stock, 
        Product.category, Product.is_available, Product.owner_id
    ]
    
    column_formatters = {
        Product.price: lambda m, a: f"¥{m.price:.2f}"
    }


class OrderAdmin(ModelView, model=Order):
    """订单管理视图"""
    name = "订单"
    name_plural = "订单管理"
    icon = "fa-solid fa-receipt"
    
    column_list = [
        Order.id, Order.user_id, Order.total_amount, 
        Order.status, Order.created_at, Order.updated_at
    ]
    column_searchable_list = [Order.status, Order.shipping_address]
    column_sortable_list = [Order.id, Order.total_amount, Order.created_at]
    column_default_sort = [(Order.id, True)]
    
    form_columns = [
        Order.user_id, Order.total_amount, Order.status, 
        Order.shipping_address, Order.notes
    ]
    
    column_formatters = {
        Order.total_amount: lambda m, a: f"¥{m.total_amount:.2f}"
    }


class OrderItemAdmin(ModelView, model=OrderItem):
    """订单项管理视图"""
    name = "订单项"
    name_plural = "订单项管理"
    icon = "fa-solid fa-list"
    
    column_list = [
        OrderItem.id, OrderItem.order_id, OrderItem.product_id, 
        OrderItem.quantity, OrderItem.unit_price
    ]
    column_sortable_list = [OrderItem.id, OrderItem.quantity, OrderItem.unit_price]
    column_default_sort = [(OrderItem.id, True)]
    
    form_columns = [
        OrderItem.order_id, OrderItem.product_id, 
        OrderItem.quantity, OrderItem.unit_price
    ]
    
    column_formatters = {
        OrderItem.unit_price: lambda m, a: f"¥{m.unit_price:.2f}"
    }


class PostAdmin(ModelView, model=Post):
    """文章管理视图"""
    name = "文章"
    name_plural = "文章管理"
    icon = "fa-solid fa-newspaper"
    
    column_list = [
        Post.id, Post.title, Post.author_id, 
        Post.is_published, Post.views, Post.created_at, Post.updated_at
    ]
    column_searchable_list = [Post.title]
    column_sortable_list = [Post.id, Post.views, Post.created_at]
    column_default_sort = [(Post.id, True)]
    
    form_columns = [Post.title, Post.content, Post.author_id, Post.is_published]
    
    column_formatters_detail = {
        Post.content: lambda m, a: m.content[:500] + "..." if len(m.content) > 500 else m.content
    }


def setup_admin(app: Admin):
    """设置Admin面板"""
    # 添加模型视图
    app.add_view(UserAdmin)
    app.add_view(ProductAdmin)
    app.add_view(OrderAdmin)
    app.add_view(OrderItemAdmin)
    app.add_view(PostAdmin)
    
    # 设置JWT认证
    secret_key = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-123456789")
    app.authentication_backend = JWTAuthenticationBackend(secret_key=secret_key)
    
    print("✅ Admin面板配置完成 - 已启用JWT认证")
