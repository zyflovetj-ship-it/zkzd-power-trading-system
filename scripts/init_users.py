#!/usr/bin/env python3
"""
初始化管理员用户脚本
创建一个默认的管理员用户用于登录
"""
import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.tools.mongo import DATABASE as db
from webapp.tools.security import get_password_hash

DEFAULT_PASSWORD = "!234qwer"

def upsert_user(username: str, password: str, email: str, full_name: str, is_superuser: bool):
    """创建或更新用户"""
    now = datetime.now()
    existing = db.users.find_one({"username": username})
    if existing:
        db.users.update_one(
            {"username": username},
            {"$set": {"hashed_password": get_password_hash(password), "updated_at": now}}
        )
        print(f"用户 '{username}' 密码已更新为: {password}")
        return

    user_doc = {
        "username": username,
        "hashed_password": get_password_hash(password),
        "email": email,
        "full_name": full_name,
        "is_active": True,
        "is_superuser": is_superuser,
        "created_at": now,
        "updated_at": now
    }
    try:
        result = db.users.insert_one(user_doc)
        print(f"成功创建用户 '{username}'（密码: {password}），ID: {result.inserted_id}")
    except Exception as e:
        print(f"创建用户 '{username}' 失败: {e}")


def create_admin_user():
    """创建/更新管理员用户"""
    password = os.getenv("ADMIN_PASSWORD", DEFAULT_PASSWORD)
    upsert_user("admin", password, "admin@example.com", "系统管理员", True)


def create_test_user():
    """创建/更新测试用户"""
    password = os.getenv("TEST_PASSWORD", DEFAULT_PASSWORD)
    upsert_user("test", password, "test@example.com", "测试用户", False)

def list_users():
    """列出所有用户"""
    try:
        users = db.users.find({})
        print(f"\n数据库中的所有用户:")
        for user in users:
            print(f"   - 用户名: {user['username']}")
            print(f"     邮箱: {user.get('email', 'N/A')}")
            print(f"     全名: {user.get('full_name', 'N/A')}")
            print(f"     激活状态: {user.get('is_active', False)}")
            print(f"     超级用户: {user.get('is_superuser', False)}")
            print(f"     创建时间: {user.get('created_at', 'N/A')}")
            print()
    except Exception as e:
        print(f"获取用户列表失败: {e}")

if __name__ == "__main__":
    print("开始初始化用户...")

    # 连接到数据库
    try:
        # 测试数据库连接
        db.list_collection_names()
        print("数据库连接成功")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)

    # 列出当前用户
    list_users()

    # 创建管理员用户
    create_admin_user()

    # 创建测试用户
    create_test_user()

    print("\n用户初始化完成！")
    print("\n登录信息:")
    print("   管理员账户: admin / !234qwer")
    print("   测试账户: test / !234qwer")