from sqladmin import ModelView
from models import User, Product, Order, OrderItem, Post
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import Response

# 简单的身份验证后端（开发用，生产环境需要替换）
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        
        # 开发环境简单验证
        if username == "admin" and password == "admin":
            request.session.update({"token": "admin-token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        # 开发环境简单验证
        if token == "admin-token":
            return True
        return False

# 用户管理
class UserAdmin(ModelView, model=User):
    name = "用户"
    name_plural = "用户管理"
    icon = "fa-solid fa-user"
    
    column_list = [User.id, User.username, User.email, User.full_name, User.is_active, User.is_admin, User.created_at]
    column_searchable_list = [User.username, User.email, User.full_name]
    column_sortable_list = [User.id, User.created_at, User.username]
    column_default_sort = [(User.id, True)]
    
    form_columns = [User.username, User.email, User.full_name, User.hashed_password, User.is_active, User.is_admin]
    
    # 页面配置
    page_size = 20
    page_size_options = [10, 20, 50, 100]

# 产品管理
class ProductAdmin(ModelView, model=Product):
    name = "产品"
    name_plural = "产品管理"
    icon = "fa-solid fa-box"
    
    column_list = [Product.id, Product.name, Product.price, Product.stock, Product.category, Product.is_available, Product.owner_id, Product.created_at]
    column_searchable_list = [Product.name, Product.category]
    column_sortable_list = [Product.id, Product.price, Product.stock, Product.created_at]
    column_default_sort = [(Product.id, True)]
    
    form_columns = [Product.name, Product.description, Product.price, Product.stock, Product.category, Product.is_available, Product.owner_id]
    
    # 格式化价格显示
    column_formatters = {
        Product.price: lambda m, a: f"¥{m.price:.2f}"
    }

# 订单管理
class OrderAdmin(ModelView, model=Order):
    name = "订单"
    name_plural = "订单管理"
    icon = "fa-solid fa-receipt"
    
    column_list = [Order.id, Order.user_id, Order.total_amount, Order.status, Order.created_at, Order.updated_at]
    column_searchable_list = [Order.status, Order.shipping_address]
    column_sortable_list = [Order.id, Order.total_amount, Order.created_at]
    column_default_sort = [(Order.id, True)]
    
    form_columns = [Order.user_id, Order.total_amount, Order.status, Order.shipping_address, Order.notes]
    
    # 格式化金额显示
    column_formatters = {
        Order.total_amount: lambda m, a: f"¥{m.total_amount:.2f}"
    }

# 订单项管理
class OrderItemAdmin(ModelView, model=OrderItem):
    name = "订单项"
    name_plural = "订单项管理"
    icon = "fa-solid fa-list"
    
    column_list = [OrderItem.id, OrderItem.order_id, OrderItem.product_id, OrderItem.quantity, OrderItem.unit_price]
    column_sortable_list = [OrderItem.id, OrderItem.quantity, OrderItem.unit_price]
    column_default_sort = [(OrderItem.id, True)]
    
    form_columns = [OrderItem.order_id, OrderItem.product_id, OrderItem.quantity, OrderItem.unit_price]
    
    # 格式化单价显示
    column_formatters = {
        OrderItem.unit_price: lambda m, a: f"¥{m.unit_price:.2f}"
    }

# 文章管理
class PostAdmin(ModelView, model=Post):
    name = "文章"
    name_plural = "文章管理"
    icon = "fa-solid fa-newspaper"
    
    column_list = [Post.id, Post.title, Post.author_id, Post.is_published, Post.views, Post.created_at, Post.updated_at]
    column_searchable_list = [Post.title]
    column_sortable_list = [Post.id, Post.views, Post.created_at]
    column_default_sort = [(Post.id, True)]
    
    form_columns = [Post.title, Post.content, Post.author_id, Post.is_published]
    
    # 内容预览
    column_formatters_detail = {
        Post.content: lambda m, a: m.content[:500] + "..." if len(m.content) > 500 else m.content
    }

def setup_admin(admin):
    """设置Admin面板"""
    # 添加模型视图
    admin.add_view(UserAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    admin.add_view(PostAdmin)
    
    # 设置身份验证（可选）
    # admin.authentication_backend = AdminAuth(secret_key="your-secret-key")
    
    print("✅ Admin面板配置完成")