"""风险监控重算定时任务（P0）"""

import logging
from typing import Any, Dict

from webapp.services.risk_monitor_service import RiskMonitorService
from webapp.tasks.base_task import BaseTask
from webapp.tools.mongo import DATABASE

logger = logging.getLogger(__name__)


class RiskMonitorTask(BaseTask):
    """执行风险数据监控 + 自动重算 + 快照 + 预警。"""

    @property
    def name(self) -> str:
        return "risk_monitor_check"

    @property
    def display_name(self) -> str:
        return "风险监控重算"

    @property
    def task_type(self) -> str:
        return "risk"

    @property
    def description(self) -> str:
        return "检查市场/电量/持仓/结算数据质量，通过后重算敞口、VaR、限额与压力测试并落快照"

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        result = RiskMonitorService(DATABASE).run()
        return {
            "delivery_date": result["delivery_date"],
            "blocked": result["blocked"],
            "checks_total": len(result["checks"]),
            "checks_failed": sum(1 for c in result["checks"] if c["level"] == "fail"),
            "snapshot_id": result["snapshot_id"],
            "alerts": len(result["alerts"]),
            "metrics": result["metrics"],
        }

    def on_success(self, result: Dict[str, Any]) -> None:
        logger.info("风险监控完成: %s", result)

    def on_failure(self, error: Exception) -> None:
        logger.error("风险监控任务失败: %s", error)
