import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from webapp.tasks.base_task import BaseTask
from webapp.tools.mongo import DATABASE

logger = logging.getLogger(__name__)


class DataCompletenessCheckTask(BaseTask):
    """数据完整度检查任务"""

    @property
    def name(self) -> str:
        return "data_completeness_check"

    @property
    def display_name(self) -> str:
        return "数据完整度检查"

    @property
    def description(self) -> str:
        return "检查负荷数据、价格数据等是否完整，识别缺失的时间点"

    @property
    def task_type(self) -> str:
        return "data_quality"

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        check_date = kwargs.get("check_date", datetime.now().strftime("%Y-%m-%d"))
        issues = []

        try:
            start = datetime.strptime(check_date, "%Y-%m-%d")
            end = start + timedelta(days=1)

            expected_points = 96

            load_count = DATABASE.user_load_data.count_documents({
                "timestamp": {"$gt": start, "$lte": end}
            })
            if load_count < expected_points:
                issues.append(f"负荷数据缺失: 期望{expected_points}点, 实际{load_count}点")

            day_ahead_count = DATABASE.day_ahead_spot_price.count_documents({
                "timestamp": {"$gt": start, "$lte": end}
            })
            if day_ahead_count < expected_points:
                issues.append(f"日前价格数据缺失: 期望{expected_points}点, 实际{day_ahead_count}点")

            real_time_count = DATABASE.real_time_spot_price.count_documents({
                "timestamp": {"$gt": start, "$lte": end}
            })
            if real_time_count < expected_points:
                issues.append(f"实时价格数据缺失: 期望{expected_points}点, 实际{real_time_count}点")

        except Exception as e:
            logger.exception(f"数据完整度检查执行失败: {e}")
            issues.append(f"检查异常: {str(e)}")

        result = {
            "check_date": check_date,
            "issues_found": len(issues),
            "issues": issues,
            "status": "pass" if not issues else "fail"
        }
        logger.info(f"数据完整度检查完成: {result['status']}, 发现{len(issues)}个问题")
        return result

    def on_success(self, result: Dict[str, Any]) -> None:
        logger.info(f"数据完整度检查成功: {result.get('status', 'unknown')}")

    def on_failure(self, error: Exception) -> None:
        logger.error(f"数据完整度检查失败: {error}", exc_info=True)


class ContractExpiryCheckTask(BaseTask):
    """合同到期检查任务"""

    @property
    def name(self) -> str:
        return "contract_expiry_check"

    @property
    def display_name(self) -> str:
        return "合同到期检查"

    @property
    def description(self) -> str:
        return "检查即将到期或已过期的合同，生成预警信息"

    @property
    def task_type(self) -> str:
        return "contract"

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        days_ahead = kwargs.get("days_ahead", 30)
        now = datetime.now()
        threshold = now + timedelta(days=days_ahead)

        try:
            expiring_soon = list(DATABASE.contracts.find({
                "end_date": {"$gte": now, "$lte": threshold},
                "status": {"$in": ["active", "pending"]}
            }))

            already_expired = list(DATABASE.contracts.find({
                "end_date": {"$lt": now},
                "status": {"$in": ["active", "pending"]}
            }))

        except Exception as e:
            logger.exception(f"合同到期检查查询失败: {e}")
            return {
                "expiring_soon_count": 0,
                "already_expired_count": 0,
                "error": str(e)
            }

        result = {
            "check_date": now.strftime("%Y-%m-%d"),
            "days_ahead": days_ahead,
            "expiring_soon_count": len(expiring_soon),
            "already_expired_count": len(already_expired),
            "expiring_contract_names": [c.get("contract_name", c.get("name", "未知")) for c in expiring_soon[:10]],
            "expired_contract_names": [c.get("contract_name", c.get("name", "未知")) for c in already_expired[:10]]
        }
        logger.info(f"合同到期检查完成: {len(expiring_soon)}个即将到期, {len(already_expired)}个已过期")
        return result

    def on_success(self, result: Dict[str, Any]) -> None:
        if result.get("already_expired_count", 0) > 0:
            logger.warning(f"存在{result['already_expired_count']}个已过期合同")

    def on_failure(self, error: Exception) -> None:
        logger.error(f"合同到期检查失败: {error}", exc_info=True)


class PriceDataSyncTask(BaseTask):
    """价格数据同步任务"""

    @property
    def name(self) -> str:
        return "price_data_sync"

    @property
    def display_name(self) -> str:
        return "价格数据同步"

    @property
    def description(self) -> str:
        return "同步日前和实时市场价格数据，确保数据一致性"

    @property
    def task_type(self) -> str:
        return "data_sync"

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        sync_date = kwargs.get("sync_date", datetime.now().strftime("%Y-%m-%d"))

        try:
            start = datetime.strptime(sync_date, "%Y-%m-%d")
            end = start + timedelta(days=1)

            day_ahead_count = DATABASE.day_ahead_spot_price.count_documents({
                "timestamp": {"$gt": start, "$lte": end}
            })
            real_time_count = DATABASE.real_time_spot_price.count_documents({
                "timestamp": {"$gt": start, "$lte": end}
            })

        except Exception as e:
            logger.exception(f"价格数据同步查询失败: {e}")
            return {
                "sync_date": sync_date,
                "error": str(e)
            }

        result = {
            "sync_date": sync_date,
            "day_ahead_points": day_ahead_count,
            "real_time_points": real_time_count,
            "is_complete": day_ahead_count >= 96 and real_time_count >= 96,
            "status": "complete" if (day_ahead_count >= 96 and real_time_count >= 96) else "incomplete"
        }
        logger.info(f"价格数据同步完成: 日前{day_ahead_count}点, 实时{real_time_count}点")
        return result

    def on_success(self, result: Dict[str, Any]) -> None:
        if not result.get("is_complete", False):
            logger.warning(f"价格数据不完整: {result.get('sync_date')}")

    def on_failure(self, error: Exception) -> None:
        logger.error(f"价格数据同步失败: {error}", exc_info=True)
