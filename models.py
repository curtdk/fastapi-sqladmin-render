"""
RBAC 权限模型
包含：角色、权限、用户-角色关联
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Table, Enum as SAEnum, Numeric
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()

# ==================== 枚举 ====================

class PermissionAction(str, enum.Enum):
    """权限动作"""
    VIEW = "view"       # 查看
    ADD = "add"         # 新增
    EDIT = "edit"       # 编辑
    DELETE = "delete"   # 删除


class BaseModel:
    """基础模型混入"""
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ==================== 原有模型（保留） ====================

class User(Base, BaseModel):
    """用户模型"""
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(200))
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)   # 超级管理员（绕过所有权限检查）
    is_superuser = Column(Boolean, default=False)
    
    # 关系
    roles = relationship("Role", secondary="user_roles", back_populates="users")
    products = relationship("Product", back_populates="owner")
    orders = relationship("Order", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def display_name(self):
        return self.username or self.email
    
    def has_perm(self, perm: str, model_name: str = None) -> bool:
        """检查用户是否有指定权限"""
        if self.is_admin or self.is_superuser:
            return True
        for role in self.roles:
            for perm_obj in role.permissions:
                if perm_obj.code == perm:
                    if model_name is None or perm_obj.model == model_name:
                        return True
        return False


class Product(Base, BaseModel):
    """产品模型"""
    __tablename__ = "products"
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2, asdecimal=False), nullable=False)
    stock = Column(Integer, default=0)
    category = Column(String(100))
    is_available = Column(Boolean, default=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    owner = relationship("User", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    
    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"


class Order(Base, BaseModel):
    """订单模型"""
    __tablename__ = "orders"
    
    user_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(Numeric(10, 2, asdecimal=False), nullable=False)
    status = Column(String(50), default="pending")
    shipping_address = Column(Text)
    notes = Column(Text)
    
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    
    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id}, total={self.total_amount})>"


class OrderItem(Base, BaseModel):
    """订单项模型"""
    __tablename__ = "order_items"
    
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2, asdecimal=False), nullable=False)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    
    def __repr__(self):
        return f"<OrderItem(id={self.id}, product={self.product_id}, quantity={self.quantity})>"


class Post(Base, BaseModel):
    """博客文章模型"""
    __tablename__ = "posts"
    
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"))
    is_published = Column(Boolean, default=False)
    views = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<Post(id={self.id}, title='{self.title[:20]}...')>"


# ==================== RBAC 模型 ====================

class Permission(Base, BaseModel):
    """权限模型"""
    __tablename__ = "permissions"
    
    name = Column(String(100), nullable=False)       # 显示名称，如"查看用户"
    code = Column(String(50), nullable=False, unique=True)  # 权限代码，如 "user.view"
    model = Column(String(50), nullable=False)       # 关联模型，如 "User"
    action = Column(String(20), nullable=False)      # 动作：view/add/edit/delete
    
    # 关系
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission(code='{self.code}')>"


class Role(Base, BaseModel):
    """角色模型"""
    __tablename__ = "roles"
    
    name = Column(String(100), nullable=False, unique=True)  # 角色名称
    code = Column(String(50), nullable=False, unique=True)   # 角色代码
    description = Column(Text)                                 # 描述
    is_active = Column(Boolean, default=True)                # 是否启用
    
    # 关系
    users = relationship("User", secondary="user_roles", back_populates="roles")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
    
    def __repr__(self):
        return f"<Role(name='{self.name}', code='{self.code}')>"
    
    def has_perm(self, code: str) -> bool:
        """检查角色是否有指定权限"""
        for perm in self.permissions:
            if perm.code == code:
                return True
        return False


# ==================== 关联表 ====================

class UserRole(Base):
    """用户-角色关联表"""
    __tablename__ = "user_roles"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    created_at = Column(DateTime, default=func.now())


class RolePermission(Base):
    """角色-权限关联表"""
    __tablename__ = "role_permissions"
    
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)
    created_at = Column(DateTime, default=func.now())


# ==================== 操作日志模型 ====================

class OperationLog(Base, BaseModel):
    """操作日志"""
    __tablename__ = "operation_logs"
    
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(100))
    action = Column(String(50))          # 操作类型：LOGIN/LOGOUT/CREATE/UPDATE/DELETE
    model = Column(String(50))           # 操作模型
    object_id = Column(String(50))        # 操作对象ID
    description = Column(Text)           # 操作描述
    ip_address = Column(String(50))       # IP地址
    user_agent = Column(Text)             # 浏览器信息
    status = Column(String(20), default="success")  # 状态：success/failed
    details = Column(Text)                # 详细信息（JSON）
    
    def __repr__(self):
        return f"<OperationLog(user={self.username}, action={self.action}, model={self.model})>"


# ==================== JWT 黑名单 ====================

class TokenBlacklist(Base):
    """JWT Token 黑名单（用于登出）"""
    __tablename__ = "token_blacklist"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token_jti = Column(String(100), unique=True, nullable=False)  # JWT ID
    user_id = Column(Integer, ForeignKey("users.id"))
    expires_at = Column(DateTime, nullable=False)  # token原始过期时间
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<TokenBlacklist(jti='{self.token_jti}')>"
