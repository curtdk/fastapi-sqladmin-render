#!/usr/bin/env python3
"""上传 RBAC 升级文件到服务器并部署"""
import os
import sys

# 文件内容
FILES = {
    "/opt/fastapi-sqladmin/models.py": "models",
    "/opt/fastapi-sqladmin/auth.py": "auth",
    "/opt/fastapi-sqladmin/admin.py": "admin",
    "/opt/fastapi-sqladmin/main.py": "main",
}

REMOTE_HOST = "root@39.105.0.212"

# 读取本地文件
def read_file(name):
    path = f"/Users/curtdk/.openclaw/workspace/rbac_upgrade/{name}.py"
    with open(path, "r") as f:
        return f.read()

# 生成 base64
import base64

for remote_path, name in FILES.items():
    content = read_file(name)
    b64 = base64.b64encode(content.encode()).decode()
    
    # 上传
    import subprocess
    cmd = f'''
python3 -c "
import base64, os
data = base64.b64decode('{b64}')
with open('{remote_path}', 'wb') as f:
    f.write(data)
print('OK: {name}')
"
'''
    result = subprocess.run(["ssh", REMOTE_HOST, cmd], capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)

print("所有文件上传完成")
