"""
SQLAdmin 集成 RBAC 权限控制
每个模型的视图都接入权限检查
"""
import os
from typing import Optional
from starlette.requests import Request

from sqladmin import ModelView, Admin, helpers
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from auth import (
    decode_token, get_db, get_user_by_id, get_user_menus,
    AsyncSessionLocal, limiter, ALLOWED_HOSTS
)
from models import User, Product, Order, OrderItem, Post, Role, Permission, OperationLog, UserRole, TokenBlacklist


# ==================== RBAC 认证后端 ====================

class RBACAuthBackend(AuthenticationBackend):
    """
    支持 RBAC 的 JWT 认证后端
    - 验证 JWT token
    - 登出时将 token 加入黑名单
    - 将用户菜单和权限传递给前端
    """
    
    async def login(self, request: Request) -> bool:
        """处理登录"""
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            return False
        
        if not username or not password:
            return False
        
        async with AsyncSessionLocal() as db:
            from auth import authenticate_user, create_access_token, log_operation, ACCESS_TOKEN_EXPIRE_MINUTES
            
            user = await authenticate_user(db, username, password)
            if not user or not user.is_active:
                return False
            
            if not user.is_admin and not user.is_superuser:
                # 非管理员不能登录后台
                return False
            
            # 创建 access token 和 refresh token
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
            
            # 记录登录日志
            await log_operation(
                db=db,
                user_id=user.id,
                username=user.username,
                action="LOGIN",
                description="管理员登录",
                request=request,
                status="success"
            )
            
            # 保存到 session
            request.session.update({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "access_jti": access_jti,
                "user_id": str(user.id),
                "username": user.username,
                "is_admin": str(user.is_admin),
                "is_superuser": str(user.is_superuser),
            })
        
        return True

    async def logout(self, request: Request) -> bool:
        """处理登出 - 将 token 加入黑名单"""
        access_jti = request.session.get("access_jti")
        user_id = request.session.get("user_id")
        
        if access_jti and user_id:
            async with AsyncSessionLocal() as db:
                from datetime import datetime, timedelta
                await log_operation(
                    db=db,
                    user_id=int(user_id),
                    username=request.session.get("username"),
                    action="LOGOUT",
                    description="管理员登出",
                    request=request,
                    status="success"
                )
                await db.execute(
                    TokenBlacklist.__table__.insert().values(
                        token_jti=access_jti,
                        user_id=int(user_id),
                        expires_at=datetime.utcnow() + timedelta(hours=24)
                    )
                )
                await db.commit()
        
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """验证请求"""
        access_token = request.session.get("access_token")
        if not access_token:
            return False
        
        try:
            from auth import is_token_blacklisted
            token_data = decode_token(access_token)
            if token_data is None:
                return False
            
            async with AsyncSessionLocal() as db:
                if await is_token_blacklisted(db, token_data.jti):
                    return False
                
                user = await get_user_by_id(db, token_data.user_id)
                if not user or not user.is_active:
                    return False
                
                if not user.is_admin and not user.is_superuser:
                    return False
                
                # 将用户信息注入 request state
                request.state.user = user
                request.state.is_admin = user.is_admin
                request.state.is_superuser = user.is_superuser
        
        except Exception:
            return False
        
        return True


# ==================== 权限混入 ====================

class RBACModelView(ModelView):
    """
    RBAC 权限控制混入
    自动根据用户角色控制：is_accessible、can_view、can_add、can_edit、can_delete
    """
    is_async = False  # 使用同步 session_maker (sqladmin 默认行为)
    
    # 权限代码前缀（子类必须定义，如 "user"、"product"）
    permission_code_prefix: str = ""
    
    async def is_accessible(self, request: Request) -> bool:
        """检查是否可访问此模型"""
        # 先检查是否已认证
        if not hasattr(request.state, "user"):
            return False
        
        user = request.state.user
        is_admin = getattr(request.state, "is_admin", False)
        is_superuser = getattr(request.state, "is_superuser", False)
        
        # 管理员/超级用户可访问
        if is_admin or is_superuser:
            return True
        
        # 检查 view 权限
        return await self._check_permission(request, "view")
    
    async def can_view(self, request: Request) -> bool:
        """检查是否可查看列表"""
        if getattr(request.state, "is_admin", False) or getattr(request.state, "is_superuser", False):
            return True
        return await self._check_permission(request, "view")
    
    async def can_add(self, request: Request) -> bool:
        """检查是否可新增"""
        if getattr(request.state, "is_admin", False) or getattr(request.state, "is_superuser", False):
            return True
        return await self._check_permission(request, "add")
    
    async def can_edit(self, request: Request) -> bool:
        """检查是否可编辑"""
        if getattr(request.state, "is_admin", False) or getattr(request.state, "is_superuser", False):
            return True
        return await self._check_permission(request, "edit")
    
    async def can_delete(self, request: Request) -> bool:
        """检查是否可删除"""
        if getattr(request.state, "is_admin", False) or getattr(request.state, "is_superuser", False):
            return True
        return await self._check_permission(request, "delete")
    
    async def _check_permission(self, request: Request, action: str) -> bool:
        """检查指定动作的权限"""
        if not self.permission_code_prefix:
            return False
        
        perm_code = f"{self.permission_code_prefix}.{action}"
        user = getattr(request.state, "user", None)
        
        if not user:
            return False
        
        for role in user.roles:
            for perm in role.permissions:
                if perm.code == perm_code:
                    return True
        
        return False
    
    async def insert_model(self, request: Request, data: dict):
        """插入时记录日志"""
        from auth import log_operation, AsyncSessionLocal
        user = getattr(request.state, "user", None)
        result = await super().insert_model(request, data)
        if user:
            async with AsyncSessionLocal() as db:
                await log_operation(
                    db=db,
                    user_id=user.id,
                    username=user.username,
                    action="CREATE",
                    model=self.model.__name__,
                    description=f"新增 {self.model.__name__}",
                    request=request,
                    status="success",
                    details={"data": {k: v for k, v in data.items() if k != "hashed_password"}}
                )
        return result
    
    async def update_model(self, request: Request, pk: dict, data: dict):
        """更新时记录日志"""
        from auth import log_operation, AsyncSessionLocal
        user = getattr(request.state, "user", None)
        result = await super().update_model(request, pk, data)
        if user:
            async with AsyncSessionLocal() as db:
                await log_operation(
                    db=db,
                    user_id=user.id,
                    username=user.username,
                    action="UPDATE",
                    model=self.model.__name__,
                    object_id=pk,
                    description=f"编辑 {self.model.__name__}",
                    request=request,
                    status="success",
                    details={"data": {k: v for k, v in data.items() if k != "hashed_password"}}
                )
        return result
    
    async def delete_model(self, request: Request, pk: dict):
        """删除时记录日志"""
        from auth import log_operation, AsyncSessionLocal
        user = getattr(request.state, "user", None)
        result = await super().delete_model(request, pk)
        if user:
            async with AsyncSessionLocal() as db:
                await log_operation(
                    db=db,
                    user_id=user.id,
                    username=user.username,
                    action="DELETE",
                    model=self.model.__name__,
                    object_id=pk,
                    description=f"删除 {self.model.__name__}",
                    request=request,
                    status="success"
                )
        return result
    
    # _get_db removed - use parent class implementation which works with is_async=False


# ==================== Admin 视图 ====================

class UserAdmin(RBACModelView, model=User):
    """用户管理视图"""
    permission_code_prefix = "user"
    name = "用户"
    name_plural = "用户管理"
    icon = "fa-solid fa-user"
    
    column_list = [
        User.id, User.username, User.email, User.full_name,
        User.is_active, User.is_admin, User.is_superuser, User.created_at
    ]
    column_searchable_list = [User.username, User.email, User.full_name]
    column_sortable_list = [User.id, User.created_at, User.username]
    column_default_sort = [(User.id, True)]
    
    form_columns = [
        User.username, User.email, User.full_name,
        User.hashed_password, User.is_active, User.is_admin, User.is_superuser
    ]
    column_details_list = [
        User.id, User.username, User.email, User.full_name,
        User.is_active, User.is_admin, User.is_superuser,
        User.created_at, User.updated_at
    ]
    
    page_size = 20
    page_size_options = [10, 20, 50, 100]
    
    form_widget_args = {
        User.hashed_password: {"type": "password", "placeholder": "留空则不修改密码"}
    }
    
    async def insert_model(self, request: Request, data: dict):
        from auth import get_password_hash
        if data.get("hashed_password"):
            data["hashed_password"] = get_password_hash(data["hashed_password"])
        return await super().insert_model(request, data)
    
    async def update_model(self, request: Request, pk: dict, data: dict):
        from auth import get_password_hash
        if data.get("hashed_password"):
            data["hashed_password"] = get_password_hash(data["hashed_password"])
        return await super().update_model(request, pk, data)


class ProductAdmin(RBACModelView, model=Product):
    permission_code_prefix = "product"
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
    column_formatters = {Product.price: lambda m, a: f"¥{m.price:.2f}"}


class OrderAdmin(RBACModelView, model=Order):
    permission_code_prefix = "order"
    name = "订单"
    name_plural = "订单管理"
    icon = "fa-solid fa-receipt"
    
    column_list = [
        Order.id, Order.user_id, Order.total_amount,
        Order.status, Order.created_at, Order.updated_at
    ]
    column_searchable_list = [Order.status]
    column_sortable_list = [Order.id, Order.total_amount, Order.created_at]
    column_default_sort = [(Order.id, True)]
    form_columns = [Order.user_id, Order.total_amount, Order.status, Order.shipping_address, Order.notes]
    column_formatters = {Order.total_amount: lambda m, a: f"¥{m.total_amount:.2f}"}


class OrderItemAdmin(RBACModelView, model=OrderItem):
    permission_code_prefix = "order_item"
    name = "订单项"
    name_plural = "订单项管理"
    icon = "fa-solid fa-list"
    
    column_list = [OrderItem.id, OrderItem.order_id, OrderItem.product_id, OrderItem.quantity, OrderItem.unit_price]
    column_sortable_list = [OrderItem.id, OrderItem.quantity, OrderItem.unit_price]
    form_columns = [OrderItem.order_id, OrderItem.product_id, OrderItem.quantity, OrderItem.unit_price]
    column_formatters = {OrderItem.unit_price: lambda m, a: f"¥{m.unit_price:.2f}"}


class PostAdmin(RBACModelView, model=Post):
    permission_code_prefix = "post"
    name = "文章"
    name_plural = "文章管理"
    icon = "fa-solid fa-newspaper"
    
    column_list = [Post.id, Post.title, Post.author_id, Post.is_published, Post.views, Post.created_at]
    column_searchable_list = [Post.title]
    column_sortable_list = [Post.id, Post.views, Post.created_at]
    form_columns = [Post.title, Post.content, Post.author_id, Post.is_published]
    column_formatters_detail = {Post.content: lambda m, a: m.content[:500] + "..." if len(m.content) > 500 else m.content}


class RoleAdmin(RBACModelView, model=Role):
    permission_code_prefix = "role"
    name = "角色"
    name_plural = "角色管理"
    icon = "fa-solid fa-shield"
    
    column_list = [Role.id, Role.name, Role.code, Role.description, Role.is_active, Role.created_at]
    column_searchable_list = [Role.name, Role.code]
    column_sortable_list = [Role.id, Role.created_at]
    form_columns = [Role.name, Role.code, Role.description, Role.is_active]
    column_details_list = [Role.id, Role.name, Role.code, Role.description, Role.is_active, Role.created_at]


class PermissionAdmin(RBACModelView, model=Permission):
    permission_code_prefix = "permission"
    name = "权限"
    name_plural = "权限管理"
    icon = "fa-solid fa-key"
    
    column_list = [Permission.id, Permission.name, Permission.code, Permission.model, Permission.action, Permission.created_at]
    column_searchable_list = [Permission.name, Permission.code, Permission.model]
    column_sortable_list = [Permission.id, Permission.model]
    form_columns = [Permission.name, Permission.code, Permission.model, Permission.action]


class OperationLogAdmin(RBACModelView, model=OperationLog):
    permission_code_prefix = "log"
    name = "日志"
    name_plural = "操作日志"
    icon = "fa-solid fa-history"
    
    column_list = [OperationLog.id, OperationLog.username, OperationLog.action, OperationLog.model, OperationLog.object_id, OperationLog.status, OperationLog.ip_address, OperationLog.created_at]
    column_searchable_list = [OperationLog.username, OperationLog.action, OperationLog.model]
    column_sortable_list = [OperationLog.id, OperationLog.created_at]
    column_default_sort = [(OperationLog.id, True)]
    
    # 日志只读，禁止增删改
    can_add = False
    can_edit = False
    can_delete = False


# ==================== 设置 Admin ====================

def setup_admin(admin: Admin):
    """配置 Admin 面板"""
    admin.add_view(UserAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    admin.add_view(PostAdmin)
    admin.add_view(RoleAdmin)
    admin.add_view(PermissionAdmin)
    admin.add_view(OperationLogAdmin)
    
    secret_key = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-123456789")
    admin.authentication_backend = RBACAuthBackend(secret_key=secret_key)
    
    print("✅ Admin 面板配置完成 - 已启用 RBAC 权限认证")
