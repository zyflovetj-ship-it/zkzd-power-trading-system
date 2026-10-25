import logging
import os


def configure_logging() -> None:
    """
    初始化全局日志配置。
    - 日志等级由环境变量 LOG_LEVEL 控制，默认 INFO
    - 统一控制台输出格式
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

