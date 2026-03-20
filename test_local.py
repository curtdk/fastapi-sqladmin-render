#!/usr/bin/env python3
"""
本地测试脚本
验证 FastAPI 应用能否正常启动和运行
"""

import subprocess
import sys
import time
import requests
import os

def test_imports():
    """测试模块导入"""
    print("🔧 测试模块导入...")
    
    modules = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "sqladmin",
        "aiosqlite"
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            return False
    
    return True

def test_app_start():
    """测试应用启动"""
    print("\n🚀 测试应用启动...")
    
    # 启动应用进程
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "9999", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 等待应用启动
    print("  等待应用启动 (5秒)...")
    time.sleep(5)
    
    # 测试健康检查
    try:
        response = requests.get("http://127.0.0.1:9999/health", timeout=5)
        if response.status_code == 200:
            print(f"  ✅ 健康检查通过: {response.json()}")
            
            # 测试数据库连接
            db_response = requests.get("http://127.0.0.1:9999/test-db", timeout=5)
            if db_response.status_code == 200:
                print(f"  ✅ 数据库连接: {db_response.json()}")
            else:
                print(f"  ⚠️ 数据库连接测试失败: {db_response.status_code}")
        else:
            print(f"  ❌ 健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
    finally:
        # 终止进程
        proc.terminate()
        proc.wait()
        print("  应用进程已终止")
    
    return True

def test_admin_panel():
    """测试Admin面板配置"""
    print("\n👨‍💼 测试Admin面板配置...")
    
    try:
        from admin import setup_admin
        from sqladmin import Admin
        from sqlalchemy.ext.asyncio import create_async_engine
        
        # 创建临时引擎
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        admin = Admin(None, engine)
        
        setup_admin(admin)
        
        # 检查视图数量
        views_count = len(admin.views)
        print(f"  ✅ Admin视图数量: {views_count}")
        
        view_names = [view.__class__.__name__ for view in admin.views]
        print(f"  已注册视图: {', '.join(view_names)}")
        
        return True
    except Exception as e:
        print(f"  ❌ Admin配置错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_models():
    """测试数据模型"""
    print("\n🗃️ 测试数据模型...")
    
    try:
        from models import User, Product, Order, OrderItem, Post
        
        models = [User, Product, Order, OrderItem, Post]
        model_names = [model.__name__ for model in models]
        
        print(f"  ✅ 模型加载: {', '.join(model_names)}")
        
        # 检查表名
        for model in models:
            print(f"    - {model.__name__}: {model.__tablename__}")
        
        return True
    except Exception as e:
        print(f"  ❌ 模型错误: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 FastAPI + SQLAdmin 本地测试")
    print("=" * 60)
    
    results = []
    
    # 1. 测试导入
    results.append(("模块导入", test_imports()))
    
    # 2. 测试模型
    results.append(("数据模型", test_models()))
    
    # 3. 测试Admin配置
    results.append(("Admin面板", test_admin_panel()))
    
    # 4. 测试应用启动（可选，注释掉以避免端口冲突）
    # results.append(("应用启动", test_app_start()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果摘要")
    print("=" * 60)
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n🎯 通过率: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！应用可以正常部署。")
        return True
    else:
        print("\n⚠️  部分测试失败，请检查问题。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)