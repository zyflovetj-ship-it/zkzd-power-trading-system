from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTask(ABC):
    """定时任务基类，所有业务任务必须继承此类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """任务唯一标识名称"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """任务显示名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """任务描述"""
        ...

    @property
    def task_type(self) -> str:
        """任务类型，子类可覆盖"""
        return "default"

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """执行任务，返回结果摘要字典"""
        ...

    def on_success(self, result: Dict[str, Any]) -> None:
        """任务成功回调"""
        pass

    def on_failure(self, error: Exception) -> None:
        """任务失败回调"""
        pass
