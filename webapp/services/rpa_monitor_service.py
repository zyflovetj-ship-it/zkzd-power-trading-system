"""
RPA 监控服务层

提供 RPA 任务执行监控相关的业务逻辑。
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pymongo.database import Database
from bson import ObjectId

logger = logging.getLogger(__name__)


class RpaMonitorService:
    """
    RPA 监控服务层

    职责：
    - 查询任务执行摘要和历史
    - 计算实时告警
    - 管理重试请求

    依赖：
    - db: MongoDB 数据库实例
    """

    # 集合名称
    RECORDS_COLLECTION = "task_execution_records"
    HISTORY_COLLECTION = "task_execution_history"
    RETRY_COLLECTION = "task_retry_requests"

    # 配置
    BATCH_GAP_MINUTES = 5  # 批次间隔分钟数
    RETRY_TIMEOUT_MINUTES = 10  # 重试超时分钟数

    def __init__(self, db: Database) -> None:
        """初始化服务"""
        self.db = db
        self.records_collection = self.db[self.RECORDS_COLLECTION]
        self.history_collection = self.db[self.HISTORY_COLLECTION]
        self.retry_collection = self.db[self.RETRY_COLLECTION]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """确保数据库索引存在"""
        try:
            # task_retry_requests 索引
            existing = {idx.get('name') for idx in self.retry_collection.list_indexes()}
            indexes = [
                ([('status', 1), ('requested_at', 1)], {'name': 'idx_status_requested'}),
                ([('pipeline_name', 1), ('task_key', 1)], {'name': 'idx_pipeline_task'}),
            ]
            for keys, options in indexes:
                if options['name'] not in existing:
                    self.retry_collection.create_index(keys, **options)
                    logger.info(f"创建索引: {options['name']}")
        except Exception as e:
            logger.warning(f"创建索引时出错: {str(e)}")

    # ========== 今日摘要 ==========

    def get_daily_summary(self, date_str: str) -> Dict[str, Any]:
        """
        获取指定日期的执行摘要

        Args:
            date_str: 日期字符串（YYYY-MM-DD）

        Returns:
            包含统计和任务列表的字典
        """
        # 查询当日摘要记录
        cursor = self.records_collection.find({"execution_date": date_str})
        tasks = list(cursor)

        if not tasks:
            return {
                "date": date_str,
                "summary": {"success": 0, "skipped": 0, "failed": 0, "alerts": 0},
                "tasks": [],
                "has_data": False
            }

        # 统计各状态数量
        success_count = sum(1 for t in tasks if t.get("daily_status") == "SUCCESS")
        skipped_count = sum(1 for t in tasks if t.get("daily_status") == "SKIPPED")
        failed_count = sum(1 for t in tasks if t.get("daily_status") == "FAILED")

        # 计算告警数量
        alerts = self.calculate_alerts(date_str)
        alert_count = len(alerts)

        # 转换任务列表
        task_list = []
        for t in tasks:
            task_list.append({
                "pipeline_name": t.get("pipeline_name", ""),
                "task_key": t.get("task_key", ""),
                "daily_status": t.get("daily_status", "FAILED"),
                "execution_time": t.get("execution_time"),
                "execution_count": t.get("execution_count", 0),
                "last_success_date": t.get("last_success_date"),
                "records_inserted": t.get("records_inserted", 0),
                "records_updated": t.get("records_updated", 0),
                "records_skipped": t.get("records_skipped", 0),
                "target_collections": t.get("target_collections", []),
                "error_message": t.get("error_message"),
                "message": t.get("message"),
                "duration_seconds": t.get("duration_seconds"),
            })

        return {
            "date": date_str,
            "summary": {
                "success": success_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "alerts": alert_count
            },
            "tasks": task_list,
            "has_data": True
        }

    # ========== 执行历史 ==========

    def get_execution_history(self, date_str: str) -> Dict[str, Any]:
        """
        获取指定日期的执行历史，按批次聚类

        Args:
            date_str: 日期字符串（YYYY-MM-DD）

        Returns:
            包含批次列表的字典
        """
        # 查询当日所有执行记录，按时间排序
        cursor = self.history_collection.find(
            {"execution_date": date_str}
        ).sort("execution_time", 1)

        records = list(cursor)

        if not records:
            return {
                "date": date_str,
                "total_batches": 0,
                "batches": [],
                "has_data": False
            }

        # 按时间间隔聚类为批次
        batches = self._cluster_into_batches(records)

        return {
            "date": date_str,
            "total_batches": len(batches),
            "batches": batches,
            "has_data": True
        }

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """
        解析时间字段，支持 datetime 对象和字符串格式

        Args:
            value: 时间值，可以是 datetime 或字符串

        Returns:
            datetime 对象，无法解析时返回 None
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # 尝试多种格式解析
            formats = [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None

    def _cluster_into_batches(self, records: List[Dict]) -> List[Dict]:
        """
        将执行记录按时间间隔聚类为批次

        规则：两条记录间隔超过5分钟则视为新批次

        Args:
            records: 按时间排序的执行记录列表

        Returns:
            批次列表
        """
        if not records:
            return []

        batches = []
        current_batch_records = []
        last_time = None

        for record in records:
            exec_time = self._parse_datetime(record.get("execution_time"))
            if not exec_time:
                continue

            # 如果与上一条记录间隔超过5分钟，开始新批次
            if last_time is not None:
                gap_seconds = (exec_time - last_time).total_seconds()
                if gap_seconds > self.BATCH_GAP_MINUTES * 60:
                    if current_batch_records:
                        batches.append(self._create_batch(len(batches) + 1, current_batch_records))
                    current_batch_records = []

            current_batch_records.append(record)
            last_time = exec_time

        # 保存最后一个批次
        if current_batch_records:
            batches.append(self._create_batch(len(batches) + 1, current_batch_records))

        return batches

    def _create_batch(self, batch_index: int, records: List[Dict]) -> Dict:
        """创建批次对象"""
        if not records:
            return {}

        start_time = records[0].get("execution_time")
        end_time = records[-1].get("execution_time")
        batch_time = start_time.strftime("%H:%M") if start_time else ""

        success_count = sum(1 for r in records if r.get("status") == "SUCCESS")
        failed_count = sum(1 for r in records if r.get("status") == "FAILED")

        # 转换记录
        record_list = []
        for r in records:
            record_list.append({
                "pipeline_name": r.get("pipeline_name", ""),
                "task_key": r.get("task_key", ""),
                "execution_time": r.get("execution_time"),
                "status": r.get("status", ""),
                "records_inserted": r.get("records_inserted", 0),
                "records_updated": r.get("records_updated", 0),
                "records_skipped": r.get("records_skipped", 0),
                "error_message": r.get("error_message"),
                "message": r.get("message"),
                "duration_seconds": r.get("duration_seconds"),
            })

        return {
            "batch_index": batch_index,
            "batch_time": batch_time,
            "start_time": start_time,
            "end_time": end_time,
            "task_count": len(records),
            "success_count": success_count,
            "failed_count": failed_count,
            "records": record_list
        }

    # ========== 告警计算 ==========

    def calculate_alerts(self, date_str: str) -> List[Dict[str, Any]]:
        """
        计算指定日期的告警（实时计算）

        告警规则：
        1. 连续失败：同一任务连续失败≥3次
        2. 长时间未更新：某任务超过24小时未成功

        Args:
            date_str: 日期字符串（YYYY-MM-DD）

        Returns:
            告警列表
        """
        alerts = []

        # 查询当日摘要
        cursor = self.records_collection.find({"execution_date": date_str})
        tasks = list(cursor)

        for task in tasks:
            pipeline_name = task.get("pipeline_name", "")
            task_key = task.get("task_key", "")
            status = task.get("daily_status", "")
            last_success = task.get("last_success_date")
            error_message = task.get("error_message")

            # 规则1：失败状态
            if status == "FAILED":
                alerts.append({
                    "level": "critical",
                    "rule": "consecutive_failure",
                    "pipeline_name": pipeline_name,
                    "task_key": task_key,
                    "message": f"任务执行失败: {error_message or '未知错误'}",
                    "timestamp": task.get("execution_time"),
                    "can_retry": True
                })

            # 规则2：长时间未成功（检查 last_success_date）
            if last_success:
                try:
                    last_success_date = datetime.strptime(last_success, "%Y-%m-%d")
                    query_date = datetime.strptime(date_str, "%Y-%m-%d")
                    days_diff = (query_date - last_success_date).days
                    if days_diff >= 3:  # 超过3天未成功
                        alerts.append({
                            "level": "warning",
                            "rule": "long_time_no_success",
                            "pipeline_name": pipeline_name,
                            "task_key": task_key,
                            "message": f"任务已{days_diff}天未成功执行，上次成功: {last_success}",
                            "timestamp": None,
                            "can_retry": True
                        })
                except (ValueError, TypeError):
                    pass

        return alerts

    # ========== 重试请求 ==========

    def create_retry_request(
        self,
        pipeline_name: str,
        task_key: str,
        operator: str
    ) -> Dict[str, Any]:
        """
        创建重试请求

        Args:
            pipeline_name: 管道名称
            task_key: 子任务标识
            operator: 操作人用户名

        Returns:
            创建的重试请求
        """
        # 检查是否已有待处理的重试请求
        existing = self.retry_collection.find_one({
            "pipeline_name": pipeline_name,
            "task_key": task_key,
            "status": {"$in": ["pending", "in_progress"]}
        })

        if existing:
            raise ValueError(f"任务 {pipeline_name}/{task_key} 已有待处理的重试请求")

        # 创建新请求
        now = datetime.now()
        doc = {
            "pipeline_name": pipeline_name,
            "task_key": task_key,
            "status": "pending",
            "requested_at": now,
            "requested_by": operator,
            "picked_up_at": None,
            "completed_at": None,
            "result_message": None
        }

        result = self.retry_collection.insert_one(doc)
        doc["_id"] = result.inserted_id

        logger.info(f"创建重试请求: {pipeline_name}/{task_key} by {operator}")

        return self._convert_retry_doc(doc)

    def get_retry_status(
        self,
        pipeline_name: str,
        task_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取重试请求状态

        Args:
            pipeline_name: 管道名称
            task_key: 子任务标识

        Returns:
            重试请求状态，不存在则返回 None
        """
        # 获取最新的重试请求
        doc = self.retry_collection.find_one(
            {"pipeline_name": pipeline_name, "task_key": task_key},
            sort=[("requested_at", -1)]
        )

        if not doc:
            return None

        # 检查是否超时
        if doc.get("status") == "in_progress":
            picked_up_at = doc.get("picked_up_at")
            if picked_up_at:
                elapsed = (datetime.now() - picked_up_at).total_seconds() / 60
                if elapsed > self.RETRY_TIMEOUT_MINUTES:
                    # 更新为超时状态
                    self.retry_collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"status": "timeout"}}
                    )
                    doc["status"] = "timeout"

        return self._convert_retry_doc(doc)

    def _convert_retry_doc(self, doc: Dict) -> Dict[str, Any]:
        """转换重试请求文档"""
        return {
            "id": str(doc["_id"]),
            "pipeline_name": doc.get("pipeline_name", ""),
            "task_key": doc.get("task_key", ""),
            "status": doc.get("status", "pending"),
            "requested_at": doc.get("requested_at"),
            "requested_by": doc.get("requested_by", ""),
            "picked_up_at": doc.get("picked_up_at"),
            "completed_at": doc.get("completed_at"),
            "result_message": doc.get("result_message"),
        }
