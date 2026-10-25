import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

#: 样例种子标记：首次读取时把原硬编码样例落库，之后全部走真实集合，
#: 保证列表行数不因写入而突变，同时留下可识别、可清理的来源标记。
SEED_FLAG = "seed_sample"


class SystemModelParametersService:
    """预测模型参数服务。

    数据源：model_params 集合。
    迁移说明：本服务原为纯硬编码样例，现改为真实读写；
    首次访问时把样例落库（带 data_source=seed_sample），避免页面数据断档。
    """

    COLLECTION = "model_params"

    def __init__(self, db) -> None:
        self.db = db

    # ---------------- 读 ----------------

    def get_models(self) -> Dict[str, Any]:
        """获取预测模型参数列表（真实集合；为空时先落种子）。"""
        self._ensure_seeded()
        docs = list(self.db[self.COLLECTION].find({}).sort([("updated_at", -1)]))
        return {"models": [self._to_public(d) for d in docs]}

    # ---------------- 写 ----------------

    def create_param(self, data: Dict[str, Any], operator: str = "system") -> Dict[str, Any]:
        """新增参数配置。名称必填且不可重复。"""
        self._ensure_seeded()
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("参数名称不能为空")
        if self.db[self.COLLECTION].count_documents({"name": name}) > 0:
            raise ValueError("参数名称已存在")
        now = datetime.now()
        doc = {
            "name": name,
            "type": data.get("type", "负荷预测"),
            "version": data.get("version", "v1.0"),
            "params": data.get("params", ""),
            "status": data.get("status", "enabled"),
            "mae": float(data.get("mae", 0) or 0),
            "data_source": "user_created",
            "created_by": operator,
            "created_at": now,
            "updated_at": now,
        }
        r = self.db[self.COLLECTION].insert_one(doc)
        doc["_id"] = r.inserted_id
        return self._to_public(doc)

    def update_param(self, param_id: str, data: Dict[str, Any], operator: str = "system") -> Dict[str, Any]:
        """更新参数配置。"""
        oid = self._to_oid(param_id)
        update = {"updated_at": datetime.now(), "updated_by": operator}
        for k in ("name", "type", "version", "params", "status", "mae"):
            if k in data:
                update[k] = data[k]
        if "mae" in update:
            update["mae"] = float(update["mae"] or 0)
        r = self.db[self.COLLECTION].update_one({"_id": oid}, {"$set": update})
        if r.matched_count == 0:
            raise ValueError("参数不存在")
        return self._to_public(self.db[self.COLLECTION].find_one({"_id": oid}))

    def delete_param(self, param_id: str) -> bool:
        """删除参数配置。"""
        oid = self._to_oid(param_id)
        return self.db[self.COLLECTION].delete_one({"_id": oid}).deleted_count > 0

    # ---------------- 内部 ----------------

    def _to_oid(self, param_id: str) -> ObjectId:
        try:
            return ObjectId(param_id)
        except Exception:
            raise ValueError("非法的参数 ID")

    @staticmethod
    def _to_public(doc: Dict[str, Any]) -> Dict[str, Any]:
        """输出字段严格对齐前端 ModelRecord 契约（camelCase）。"""
        upd = doc.get("updated_at")
        return {
            "id": str(doc.get("_id", "")),
            "name": doc.get("name", ""),
            "type": doc.get("type", ""),
            "version": doc.get("version", ""),
            "params": doc.get("params", ""),
            "status": doc.get("status", "enabled"),
            "mae": doc.get("mae", 0),
            "updatedAt": upd.strftime("%Y-%m-%d %H:%M") if isinstance(upd, datetime) else str(upd or ""),
            "dataSource": doc.get("data_source", ""),
        }

    def _ensure_seeded(self) -> None:
        """集合为空时落一份种子样例，保持页面连续性与可追溯性。"""
        if self.db[self.COLLECTION].count_documents({}) > 0:
            return
        seeds: List[Dict[str, Any]] = [
            {"name": "LSTM-负荷-基线", "type": "负荷预测", "version": "v2.3", "params": "学习率=0.001, 窗口长度=96, 隐藏层=64", "status": "enabled", "mae": 42.6},
            {"name": "XGBoost-负荷", "type": "负荷预测", "version": "v1.8", "params": "最大深度=8, 树数=300, 学习率=0.05", "status": "enabled", "mae": 51.2},
            {"name": "Prophet-价格", "type": "价格预测", "version": "v1.2", "params": "季节周期=日/周, 变更点=0.05", "status": "enabled", "mae": 18.9},
            {"name": "LightGBM-负荷", "type": "负荷预测", "version": "v2.1", "params": "最大深度=10, 树数=400, 学习率=0.03", "status": "enabled", "mae": 47.8},
            {"name": "ARIMA-价格", "type": "价格预测", "version": "v1.0", "params": "阶数=(5,1,2)", "status": "disabled", "mae": 29.4},
            {"name": "Transformer-负荷", "type": "负荷预测", "version": "v1.5", "params": "层数=4, 头数=8, 维度=128", "status": "enabled", "mae": 38.1},
            {"name": "GRU-负荷", "type": "负荷预测", "version": "v1.3", "params": "隐藏层=48, 层数=2", "status": "enabled", "mae": 44.7},
            {"name": "XGBoost-价格", "type": "价格预测", "version": "v2.0", "params": "最大深度=6, 树数=500, 学习率=0.04", "status": "disabled", "mae": 22.6},
        ]
        now = datetime.now()
        docs = [
            {**s, "data_source": SEED_FLAG, "created_by": "system", "created_at": now, "updated_at": now}
            for s in seeds
        ]
        self.db[self.COLLECTION].insert_many(docs)
        logger.info("model_params 为空，已落 %d 条种子样例(data_source=%s)", len(docs), SEED_FLAG)
