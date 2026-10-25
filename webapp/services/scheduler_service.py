import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from webapp.tools.mongo import DATABASE
from webapp.tasks.registry import registry
from webapp.tasks.base_task import BaseTask
from webapp.tasks.business_tasks import (
    DataCompletenessCheckTask,
    ContractExpiryCheckTask,
    PriceDataSyncTask,
)

logger = logging.getLogger(__name__)

TASK_CONFIGS_COLLECTION = "task_configs"
EXECUTION_LOGS_COLLECTION = "task_execution_logs"


class SchedulerService:
    """调度中心服务，管理APScheduler和任务持久化"""

    def __init__(self, db) -> None:
        self.db = db
        self.scheduler: Optional[BackgroundScheduler] = None
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """确保数据库索引存在"""
        try:
            self.db[TASK_CONFIGS_COLLECTION].create_index(
                [("name", 1)], unique=True
            )
            self.db[TASK_CONFIGS_COLLECTION].create_index([("task_type", 1)])
            self.db[TASK_CONFIGS_COLLECTION].create_index([("is_enabled", 1)])

            self.db[EXECUTION_LOGS_COLLECTION].create_index(
                [("task_name", 1), ("started_at", -1)]
            )
            self.db[EXECUTION_LOGS_COLLECTION].create_index([("status", 1)])
            self.db[EXECUTION_LOGS_COLLECTION].create_index([("started_at", -1)])
            logger.info("调度器索引创建完成")
        except Exception as e:
            logger.error(f"创建调度器索引失败: {e}", exc_info=True)

    def _register_default_tasks(self) -> None:
        """注册默认业务任务"""
        for task_class in [DataCompletenessCheckTask, ContractExpiryCheckTask, PriceDataSyncTask]:
            registry.register(task_class)

    def _sync_configs_to_db(self) -> None:
        """将注册的任务同步到数据库配置"""
        for task in registry.list_all():
            existing = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task.name})
            if not existing:
                config_doc = {
                    "name": task.name,
                    "display_name": task.display_name,
                    "description": task.description,
                    "task_type": task.task_type,
                    "is_enabled": False,
                    "schedule_config": {
                        "trigger_type": "cron",
                        "cron_expression": None,
                        "interval_seconds": None,
                        "run_at": None,
                    },
                    "retry_config": {"max_retries": 3, "retry_delay_seconds": 60},
                    "alert_config": {
                        "on_failure": True,
                        "on_success": False,
                        "alert_level": "P2",
                    },
                    "last_run_at": None,
                    "last_run_status": None,
                    "next_run_at": None,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "created_by": "system",
                    "updated_by": "system",
                }
                self.db[TASK_CONFIGS_COLLECTION].insert_one(config_doc)
                logger.info(f"同步任务配置到数据库: {task.name}")

    def start(self) -> None:
        """启动调度器"""
        if self.scheduler and self.scheduler.running:
            logger.warning("调度器已在运行中")
            return

        self._register_default_tasks()
        self._sync_configs_to_db()

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("APScheduler 已启动")

        enabled_configs = list(
            self.db[TASK_CONFIGS_COLLECTION].find({"is_enabled": True})
        )
        for config in enabled_configs:
            self._add_job_to_scheduler(config)
        logger.info(f"已加载 {len(enabled_configs)} 个启用的定时任务")

    def stop(self) -> None:
        """停止调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler 已停止")

    def _build_trigger(self, schedule_config: Dict[str, Any]):
        """根据调度配置构建APScheduler触发器"""
        trigger_type = schedule_config.get("trigger_type", "cron")
        if trigger_type == "cron":
            cron_expr = schedule_config.get("cron_expression")
            if cron_expr:
                parts = cron_expr.split()
                if len(parts) == 5:
                    return CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4],
                    )
            return CronTrigger(hour=8, minute=0)
        elif trigger_type == "interval":
            seconds = schedule_config.get("interval_seconds", 3600)
            return IntervalTrigger(seconds=seconds)
        elif trigger_type == "date":
            run_at = schedule_config.get("run_at")
            if run_at:
                run_time = run_at if isinstance(run_at, datetime) else datetime.fromisoformat(str(run_at))
                return DateTrigger(run_date=run_time)
            return DateTrigger(run_date=datetime.now())
        else:
            raise ValueError(f"不支持的触发类型: {trigger_type}")

    def _add_job_to_scheduler(self, config: Dict[str, Any]) -> None:
        """将任务配置添加到APScheduler"""
        task_name = config["name"]
        task = registry.get(task_name)
        if not task:
            logger.warning(f"任务 '{task_name}' 未注册，跳过添加")
            return

        # 防御：APScheduler 尚未初始化时给出明确错误，
        # 而不是让 None.get_job 抛 AttributeError 被下面的 except 静默吞掉，
        # 导致"API 上改期/启停成功、实际调度器里没变"的假象。
        if self.scheduler is None:
            raise ValueError("调度器未运行（SchedulerService.start() 尚未被调用），任务配置未生效")

        try:
            trigger = self._build_trigger(config.get("schedule_config", {}))
            job_id = f"scheduler_{task_name}"

            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            self.scheduler.add_job(
                self._execute_task_wrapper,
                trigger=trigger,
                id=job_id,
                args=[task_name, "scheduled", None],
                replace_existing=True,
            )

            next_run = None
            job = self.scheduler.get_job(job_id)
            if job and job.next_run_time:
                next_run = job.next_run_time.replace(tzinfo=None)

            self.db[TASK_CONFIGS_COLLECTION].update_one(
                {"name": task_name},
                {"$set": {"next_run_at": next_run, "updated_at": datetime.now()}},
            )
            logger.info(f"已添加调度任务: {task_name}")
        except Exception as e:
            logger.error(f"添加调度任务失败 '{task_name}': {e}", exc_info=True)

    def _execute_task_wrapper(
        self, task_name: str, trigger_type: str = "scheduled", triggered_by: Optional[str] = None
    ) -> None:
        """包装任务执行，记录日志和异常"""
        task = registry.get(task_name)
        if not task:
            logger.error(f"任务 '{task_name}' 未注册")
            return

        config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
        is_enabled = config.get("is_enabled", False) if config else False

        if trigger_type == "scheduled" and not is_enabled:
            self._write_log(
                task_name=task_name,
                task_type=task.task_type,
                status="skipped",
                started_at=datetime.now(),
                finished_at=datetime.now(),
                duration_ms=0,
                result_summary="任务已禁用，跳过执行",
                trigger_type=trigger_type,
                triggered_by=triggered_by,
            )
            return

        started_at = datetime.now()
        log_id = self._write_log(
            task_name=task_name,
            task_type=task.task_type,
            status="running",
            started_at=started_at,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
        )

        retry_config = config.get("retry_config", {}) if config else {}
        max_retries = retry_config.get("max_retries", 3)
        retry_delay = retry_config.get("retry_delay_seconds", 60)

        last_error = None
        # 必须在 except 块**内部**捕获 traceback：
        # 否则循环结束后再调用 traceback.format_exc() 只会拿到 "NoneType: None"，排障信息全丢。
        last_error_tb: Optional[str] = None
        result = None

        for attempt in range(max_retries + 1):
            try:
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(task.execute())
                finally:
                    loop.close()

                task.on_success(result)
                finished_at = datetime.now()
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)

                self.db[TASK_CONFIGS_COLLECTION].update_one(
                    {"name": task_name},
                    {
                        "$set": {
                            "last_run_at": finished_at,
                            "last_run_status": "success",
                            "updated_at": datetime.now(),
                        }
                    },
                )

                self._update_log(
                    log_id=log_id,
                    status="success",
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    result_summary=str(result)[:500] if result else None,
                )
                logger.info(f"任务 '{task_name}' 执行成功 (尝试 {attempt + 1}/{max_retries + 1})")
                return

            except Exception as e:
                last_error = e
                last_error_tb = traceback.format_exc()
                logger.warning(
                    f"任务 '{task_name}' 执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}",
                    exc_info=True,
                )
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    # 在 except 块内回调，业务侧的 logger.error(..., exc_info=True) 才能取到真实堆栈
                    task.on_failure(e)

        # 注：task.on_failure 已在上方 except 块内（最后一次重试失败时）调用，
        # 以便业务侧 logger.error(..., exc_info=True) 能取到真实堆栈。
        finished_at = datetime.now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        self.db[TASK_CONFIGS_COLLECTION].update_one(
            {"name": task_name},
            {
                "$set": {
                    "last_run_at": finished_at,
                    "last_run_status": "failed",
                    "updated_at": datetime.now(),
                }
            },
        )

        self._update_log(
            log_id=log_id,
            status="failed",
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_message=str(last_error)[:500] if last_error else None,
            # 使用在 except 块内捕获的堆栈；此前直接调用 traceback.format_exc()
            # 拿到的恒为 "NoneType: None"
            error_traceback=(last_error_tb or "")[:2000] or None,
        )
        logger.error(
            f"任务 '{task_name}' 最终执行失败: {last_error}",
            exc_info=last_error if last_error is not None else None,
        )

    def _write_log(
        self,
        task_name: str,
        task_type: str,
        status: str,
        started_at: datetime,
        finished_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
        trigger_type: str = "scheduled",
        triggered_by: Optional[str] = None,
    ) -> str:
        """写入执行日志"""
        doc = {
            "task_name": task_name,
            "task_type": task_type,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "result_summary": result_summary,
            "error_message": error_message,
            "error_traceback": error_traceback,
            "trigger_type": trigger_type,
            "triggered_by": triggered_by,
            "created_at": datetime.now(),
        }
        result = self.db[EXECUTION_LOGS_COLLECTION].insert_one(doc)
        return str(result.inserted_id)

    def _update_log(
        self,
        log_id: str,
        status: str,
        finished_at: datetime,
        duration_ms: Optional[int] = None,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
    ) -> None:
        """更新执行日志"""
        from bson import ObjectId

        update_fields = {
            "status": status,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
        }
        if result_summary is not None:
            update_fields["result_summary"] = result_summary
        if error_message is not None:
            update_fields["error_message"] = error_message
        if error_traceback is not None:
            update_fields["error_traceback"] = error_traceback

        self.db[EXECUTION_LOGS_COLLECTION].update_one(
            {"_id": ObjectId(log_id)}, {"$set": update_fields}
        )

    def add_job(self, task_name: str, schedule_config: Dict[str, Any], operator: str = "system") -> None:
        """添加定时任务"""
        task = registry.get(task_name)
        if not task:
            raise ValueError(f"任务 '{task_name}' 未注册")

        config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
        if not config:
            raise ValueError(f"任务配置 '{task_name}' 不存在")

        self.db[TASK_CONFIGS_COLLECTION].update_one(
            {"name": task_name},
            {
                "$set": {
                    "schedule_config": schedule_config,
                    "updated_at": datetime.now(),
                    "updated_by": operator,
                }
            },
        )

        updated_config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
        if updated_config.get("is_enabled"):
            self._add_job_to_scheduler(updated_config)

    def remove_job(self, task_name: str) -> None:
        """移除定时任务（从调度器中移除，数据库配置保留但禁用）"""
        job_id = f"scheduler_{task_name}"
        if self.scheduler and self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.db[TASK_CONFIGS_COLLECTION].update_one(
            {"name": task_name},
            {"$set": {"is_enabled": False, "next_run_at": None, "updated_at": datetime.now()}},
        )

    def trigger_job(self, task_name: str, triggered_by: str = "manual") -> Dict[str, Any]:
        """手动触发任务"""
        task = registry.get(task_name)
        if not task:
            raise ValueError(f"任务 '{task_name}' 未注册")

        if self.scheduler and self.scheduler.running:
            self.scheduler.add_job(
                self._execute_task_wrapper,
                id=f"manual_{task_name}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                args=[task_name, "manual", triggered_by],
            )
            return {"task_name": task_name, "status": "triggered", "message": "任务已手动触发"}
        else:
            raise ValueError(
                "调度器未运行，无法手动触发。"
                "请确认应用启动流程已调用 SchedulerService.start()，"
                "且 API 层与后台任务共用同一实例。"
            )

    def toggle_job(self, task_name: str, is_enabled: bool, operator: str = "system") -> None:
        """启用/禁用任务"""
        config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
        if not config:
            raise ValueError(f"任务配置 '{task_name}' 不存在")

        self.db[TASK_CONFIGS_COLLECTION].update_one(
            {"name": task_name},
            {
                "$set": {
                    "is_enabled": is_enabled,
                    "updated_at": datetime.now(),
                    "updated_by": operator,
                }
            },
        )

        if is_enabled:
            updated_config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
            self._add_job_to_scheduler(updated_config)
        else:
            job_id = f"scheduler_{task_name}"
            if self.scheduler and self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            self.db[TASK_CONFIGS_COLLECTION].update_one(
                {"name": task_name},
                {"$set": {"next_run_at": None, "updated_at": datetime.now()}},
            )

    def list_tasks(
        self,
        task_type: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取任务配置列表"""
        query = {}
        if task_type is not None:
            query["task_type"] = task_type
        if is_enabled is not None:
            query["is_enabled"] = is_enabled

        total = self.db[TASK_CONFIGS_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            self.db[TASK_CONFIGS_COLLECTION]
            .find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(page_size)
        )

        items = []
        for doc in cursor:
            items.append(
                {
                    "id": str(doc["_id"]),
                    "name": doc["name"],
                    "display_name": doc["display_name"],
                    "description": doc.get("description", ""),
                    "task_type": doc["task_type"],
                    "is_enabled": doc["is_enabled"],
                    "schedule_config": doc.get("schedule_config", {}),
                    "last_run_at": doc.get("last_run_at"),
                    "last_run_status": doc.get("last_run_status"),
                    "next_run_at": doc.get("next_run_at"),
                    "updated_at": doc.get("updated_at"),
                }
            )

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def get_task(self, task_name: str) -> Optional[Dict[str, Any]]:
        """获取任务配置详情"""
        doc = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
        if not doc:
            return None
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        return doc

    def update_task(
        self, task_name: str, update_data: Dict[str, Any], operator: str = "system"
    ) -> Optional[Dict[str, Any]]:
        """更新任务配置"""
        config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
        if not config:
            raise ValueError(f"任务配置 '{task_name}' 不存在")

        set_fields = {"updated_at": datetime.now(), "updated_by": operator}
        for key, value in update_data.items():
            if value is not None:
                set_fields[key] = value

        self.db[TASK_CONFIGS_COLLECTION].update_one(
            {"name": task_name}, {"$set": set_fields}
        )

        if "schedule_config" in set_fields and config.get("is_enabled"):
            updated_config = self.db[TASK_CONFIGS_COLLECTION].find_one({"name": task_name})
            self._add_job_to_scheduler(updated_config)

        return self.get_task(task_name)

    def get_execution_logs(
        self,
        task_name: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取执行日志"""
        query = {"task_name": task_name}
        if status:
            query["status"] = status

        total = self.db[EXECUTION_LOGS_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            self.db[EXECUTION_LOGS_COLLECTION]
            .find(query)
            .sort("started_at", -1)
            .skip(skip)
            .limit(page_size)
        )

        items = []
        for doc in cursor:
            items.append(
                {
                    "id": str(doc["_id"]),
                    "task_name": doc["task_name"],
                    "task_type": doc["task_type"],
                    "status": doc["status"],
                    "started_at": doc["started_at"],
                    "finished_at": doc.get("finished_at"),
                    "duration_ms": doc.get("duration_ms"),
                    "result_summary": doc.get("result_summary"),
                    "error_message": doc.get("error_message"),
                    "trigger_type": doc.get("trigger_type", "scheduled"),
                    "triggered_by": doc.get("triggered_by"),
                }
            )

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计概览"""
        total_tasks = self.db[TASK_CONFIGS_COLLECTION].count_documents({})
        enabled_tasks = self.db[TASK_CONFIGS_COLLECTION].count_documents({"is_enabled": True})
        disabled_tasks = total_tasks - enabled_tasks

        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_success = self.db[EXECUTION_LOGS_COLLECTION].count_documents(
            {"status": "success", "started_at": {"$gte": recent_cutoff}}
        )
        recent_failed = self.db[EXECUTION_LOGS_COLLECTION].count_documents(
            {"status": "failed", "started_at": {"$gte": recent_cutoff}}
        )
        recent_running = self.db[EXECUTION_LOGS_COLLECTION].count_documents(
            {"status": "running", "started_at": {"$gte": recent_cutoff}}
        )

        return {
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "disabled_tasks": disabled_tasks,
            "recent_success_count": recent_success,
            "recent_failed_count": recent_failed,
            "recent_running_count": recent_running,
        }

    def get_trend(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取执行趋势数据"""
        start_date = datetime.now() - timedelta(days=days)

        pipeline = [
            {"$match": {"started_at": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$started_at"}
                    },
                    "total_count": {"$sum": 1},
                    "success_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                    },
                    "failed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ]

        results = list(self.db[EXECUTION_LOGS_COLLECTION].aggregate(pipeline))

        trend = []
        all_dates = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            all_dates.append(d)

        date_result_map = {r["_id"]: r for r in results}

        for d in all_dates:
            r = date_result_map.get(d, {})
            total = r.get("total_count", 0)
            success = r.get("success_count", 0)
            failed = r.get("failed_count", 0)
            success_rate = round(success / total * 100, 1) if total > 0 else 0.0
            trend.append(
                {
                    "date": d,
                    "total_count": total,
                    "success_count": success,
                    "failed_count": failed,
                    "success_rate": success_rate,
                }
            )

        return trend
