import logging
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from pymongo.database import Database

from webapp.models.user_management import UserListItem, UserListResponse
from webapp.tools.security import get_password_hash

logger = logging.getLogger(__name__)

ROLES = ['管理员', '交易员', '风控', '只读']


class SystemUsersService:

    def __init__(self, db: Database) -> None:
        self.db = db
        self.collection = self.db.users
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            existing = {idx.get('name') for idx in self.collection.list_indexes()}
            if 'idx_users_username' not in existing:
                self.collection.create_index([('username', 1)], unique=True, name='idx_users_username')
        except Exception as exc:
            logger.warning("创建用户索引时出错: %s", exc)

    def get_users(self, keyword: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if keyword:
            query["$or"] = [
                {"username": {"$regex": keyword, "$options": "i"}},
                {"full_name": {"$regex": keyword, "$options": "i"}},
            ]
        total = self.collection.count_documents(query)
        skip = (page - 1) * page_size
        docs = list(self.collection.find(
            query, {"hashed_password": 0}
        ).sort("created_at", -1).skip(skip).limit(page_size))
        items = []
        for doc in docs:
            items.append(UserListItem(
                id=str(doc["_id"]),
                username=doc.get("username", ""),
                full_name=doc.get("full_name"),
                email=doc.get("email"),
                department=doc.get("department"),
                role=doc.get("role", "只读"),
                is_active=doc.get("is_active", True),
                last_login=doc.get("last_login"),
                created_at=doc.get("created_at"),
            ))
        return UserListResponse(total=total, items=items).model_dump()

    def create_user(self, user_data: Dict[str, Any], operator: str) -> Dict[str, Any]:
        existing = self.collection.find_one({"username": user_data["username"]})
        if existing:
            raise ValueError(f"用户名 '{user_data['username']}' 已存在")

        password = user_data.pop("password")
        doc = {
            "username": user_data["username"],
            "full_name": user_data.get("full_name"),
            "email": user_data.get("email"),
            "department": user_data.get("department"),
            "role": user_data.get("role", "交易员"),
            "hashed_password": get_password_hash(password),
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "created_by": operator,
        }
        result = self.collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc.pop("hashed_password", None)
        doc.pop("_id", None)
        return doc

    def update_user(self, user_id: str, update_data: Dict[str, Any], operator: str) -> Dict[str, Any]:
        if not ObjectId.is_valid(user_id):
            raise ValueError("无效的用户ID")
        existing = self.collection.find_one({"_id": ObjectId(user_id)})
        if not existing:
            raise ValueError("用户不存在")

        update_data["updated_at"] = datetime.now()
        update_data["updated_by"] = operator
        self.collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})

        doc = self.collection.find_one({"_id": ObjectId(user_id)}, {"hashed_password": 0})
        doc["id"] = str(doc.pop("_id"))
        return doc

    def delete_user(self, user_id: str) -> None:
        if not ObjectId.is_valid(user_id):
            raise ValueError("无效的用户ID")
        result = self.collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise ValueError("用户不存在")

    def reset_password(self, user_id: str, new_password: str) -> None:
        if not ObjectId.is_valid(user_id):
            raise ValueError("无效的用户ID")
        existing = self.collection.find_one({"_id": ObjectId(user_id)})
        if not existing:
            raise ValueError("用户不存在")
        self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": get_password_hash(new_password), "updated_at": datetime.now()}}
        )
