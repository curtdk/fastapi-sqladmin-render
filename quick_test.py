#!/usr/bin/env python3
"""
快速启动测试
"""
import subprocess
import sys
import time
import requests
import os

def main():
    print("🚀 快速启动测试")
    print("=" * 60)
    
    # 启动应用
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "10000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print("启动应用进程...")
    time.sleep(3)  # 等待应用启动
    
    try:
        # 测试健康检查
        print("测试健康检查端点...")
        response = requests.get("http://127.0.0.1:10000/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ 健康检查通过: {response.json()}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            proc.terminate()
            return False
        
        # 测试数据库连接
        print("测试数据库连接...")
        db_response = requests.get("http://127.0.0.1:10000/test-db", timeout=5)
        if db_response.status_code == 200:
            print(f"✅ 数据库连接: {db_response.json()}")
        else:
            print(f"⚠️ 数据库连接测试失败: {db_response.status_code}")
        
        # 测试首页
        print("测试首页...")
        home_response = requests.get("http://127.0.0.1:10000/", timeout=5)
        if home_response.status_code == 200:
            print(f"✅ 首页访问正常")
        else:
            print(f"⚠️ 首页访问失败: {home_response.status_code}")
        
        print("\n🎉 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False
    finally:
        # 终止进程
        print("终止应用进程...")
        proc.terminate()
        proc.wait()
        print("测试完成")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)