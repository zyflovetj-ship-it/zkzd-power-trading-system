import logging
from typing import Dict, List, Optional, Type

from webapp.tasks.base_task import BaseTask

logger = logging.getLogger(__name__)


class TaskRegistry:
    """任务注册中心，单例模式"""

    _instance: Optional["TaskRegistry"] = None
    _tasks: Dict[str, BaseTask]

    def __new__(cls) -> "TaskRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
        return cls._instance

    def register(self, task_class: Type[BaseTask]) -> None:
        """注册任务类，自动实例化"""
        task = task_class()
        if task.name in self._tasks:
            logger.warning(f"任务 '{task.name}' 已注册，将被覆盖")
        self._tasks[task.name] = task
        logger.info(f"注册任务: {task.name} ({task.display_name})")

    def get(self, name: str) -> Optional[BaseTask]:
        """按名称获取任务实例"""
        return self._tasks.get(name)

    def list_all(self) -> List[BaseTask]:
        """获取所有已注册任务"""
        return list(self._tasks.values())

    def list_by_type(self, task_type: str) -> List[BaseTask]:
        """按类型获取任务列表"""
        return [t for t in self._tasks.values() if t.task_type == task_type]

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None


registry = TaskRegistry()
