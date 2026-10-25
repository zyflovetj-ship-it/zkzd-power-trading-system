import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from pymongo.database import Database

from webapp.models.dashboard import (
    DashboardData,
    DashboardKPI,
    DailyElectricityItem,
    ContractStatusItem,
    RecentActivityItem,
)
from webapp.models.contract import calculate_contract_status

logger = logging.getLogger(__name__)


class DashboardService:

    def __init__(self, db: Database) -> None:
        self.db = db
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            existing = {idx.get("name") for idx in self.db.customers.list_indexes()}
            if "idx_customer_status" not in existing:
                self.db.customers.create_index(
                    [("status", 1)], name="idx_customer_status"
                )
        except Exception as exc:
            logger.warning("创建Dashboard索引时出错: %s", exc)

    def get_dashboard_data(self) -> Dict[str, Any]:
        kpi = self._calculate_kpi()
        daily_electricity = self._get_daily_electricity()
        contract_status = self._get_contract_status()
        recent_activities = self._get_recent_activities()
        return DashboardData(
            kpi=kpi,
            daily_electricity=daily_electricity,
            contract_status=contract_status,
            recent_activities=recent_activities,
        ).model_dump()

    def _calculate_kpi(self) -> DashboardKPI:
        try:
            customer_count = self.db.customers.count_documents({})
            active_customer_count = self.db.customers.count_documents(
                {"status": "active"}
            )
        except Exception:
            customer_count = 0
            active_customer_count = 0

        contract_count = 0
        active_contract_count = 0
        try:
            for doc in self.db.retail_contracts.find(
                {},
                {
                    "purchase_start_month": 1,
                    "purchase_end_month": 1,
                },
            ):
                contract_count += 1
                start = doc.get("purchase_start_month")
                end = doc.get("purchase_end_month")
                if start and end:
                    status = calculate_contract_status(start, end)
                    if status == "active":
                        active_contract_count += 1
        except Exception as exc:
            logger.warning("统计合同状态失败: %s", exc)

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        today_electricity = 0.0
        try:
            pipeline = [
                {"$match": {"timestamp": {"$gt": today, "$lte": tomorrow}}},
                {"$group": {"_id": None, "total": {"$sum": "$value"}}},
            ]
            result = list(self.db.user_load_data.aggregate(pipeline))
            if result:
                today_electricity = round(result[0]["total"], 2)
        except Exception:
            pass

        total_cost = 0.0
        saving_rate = 0.0
        try:
            pipeline_cost = [
                {"$group": {"_id": None, "total": {"$sum": "$value"}}}
            ]
            cost_result = list(self.db.user_load_data.aggregate(pipeline_cost))
            if cost_result:
                total_cost = round(cost_result[0]["total"] * 0.5, 2)
            if total_cost > 0:
                saving_rate = round((1 - 0.85) * 100, 2)
        except Exception:
            pass

        return DashboardKPI(
            customer_count=customer_count,
            active_customer_count=active_customer_count,
            contract_count=contract_count,
            active_contract_count=active_contract_count,
            today_electricity=today_electricity,
            total_cost=total_cost,
            saving_rate=saving_rate,
        )

    def _get_daily_electricity(self) -> List[DailyElectricityItem]:
        items: List[DailyElectricityItem] = []
        try:
            end_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            start_date = end_date - timedelta(days=30)
            pipeline = [
                {"$match": {"timestamp": {"$gt": start_date, "$lte": end_date}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$timestamp",
                            }
                        },
                        "total": {"$sum": "$value"},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
            results = list(self.db.user_load_data.aggregate(pipeline))
            for r in results:
                items.append(
                    DailyElectricityItem(date=r["_id"], value=round(r["total"], 2))
                )
        except Exception as exc:
            logger.warning("获取日电量趋势失败: %s", exc)
        return items

    def _get_contract_status(self) -> List[ContractStatusItem]:
        items: List[ContractStatusItem] = []
        try:
            status_counts: Dict[str, int] = {"pending": 0, "active": 0, "expired": 0}
            for doc in self.db.retail_contracts.find(
                {},
                {
                    "purchase_start_month": 1,
                    "purchase_end_month": 1,
                },
            ):
                start = doc.get("purchase_start_month")
                end = doc.get("purchase_end_month")
                if start and end:
                    status = calculate_contract_status(start, end)
                else:
                    status = "pending"
                status_counts[status] = status_counts.get(status, 0) + 1
            for status, count in status_counts.items():
                if count > 0:
                    items.append(ContractStatusItem(status=status, count=count))
        except Exception as exc:
            logger.warning("获取合同状态分布失败: %s", exc)
        return items

    def _get_recent_activities(self) -> List[RecentActivityItem]:
        items: List[RecentActivityItem] = []
        try:
            recent = (
                self.db.customers.find(
                    {"updated_at": {"$exists": True}},
                    {"_id": 1, "user_name": 1, "status": 1, "updated_at": 1},
                )
                .sort("updated_at", -1)
                .limit(5)
            )
            for r in recent:
                items.append(
                    RecentActivityItem(
                        id=str(r["_id"]),
                        type="客户",
                        description=f"{r.get('user_name', '未知')} 状态更新为 {r.get('status', '未知')}",
                        timestamp=r.get("updated_at", datetime.now()),
                    )
                )
        except Exception as exc:
            logger.warning("获取最近动态失败: %s", exc)
        return items