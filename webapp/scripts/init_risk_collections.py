"""
风险域集合与索引初始化（P0）

用法：
    cd /data/zk-App/zk-energy-new && python -m webapp.scripts.init_risk_collections

只创建集合与索引，不写入业务数据，可重复执行（幂等）。
"""

import logging
import sys
from typing import Any, Dict, List, Tuple

from pymongo import ASCENDING, DESCENDING

from webapp.tools.mongo import DATABASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# (集合名, [(字段, 方向, 索引名)], 说明)
# (集合名, [(索引键, 是否唯一, 索引名)], 说明)
# 注意：unique 只用于业务主键。把时间戳/日期类索引设成 unique 会导致
# 同一毫秒只能写入一条记录（曾导致 risk_alert_event 批量写入 E11000）。
COLLECTIONS: List[Tuple[str, List[Tuple[Any, bool, str]], str]] = [
    (
        "risk_position",
        [
            ([("portfolio_id", ASCENDING), ("delivery_ts", ASCENDING)], False, "idx_risk_position_portfolio_ts"),
            ([("customer_id", ASCENDING), ("delivery_ts", ASCENDING)], False, "idx_risk_position_customer_ts"),
            ([("source", ASCENDING), ("delivery_ts", ASCENDING)], False, "idx_risk_position_source_ts"),
        ],
        "持仓明细：按交割时段切分，source ∈ 中长期/现货/实时/零售",
    ),
    (
        "risk_metric_snapshot",
        [
            ([("as_of", DESCENDING)], False, "idx_snapshot_as_of"),
            ([("delivery_date", ASCENDING), ("as_of", DESCENDING)], False, "idx_snapshot_delivery"),
            ([("data_fingerprint", ASCENDING)], False, "idx_snapshot_fingerprint"),
        ],
        "指标快照：只追加不覆盖，保证可回溯复现",
    ),
    (
        "risk_limit",
        [
            ([("enabled", ASCENDING), ("limit_type", ASCENDING)], False, "idx_limit_enabled_type"),
            ([("limit_id", ASCENDING)], True, "idx_limit_id"),
        ],
        "限额定义：scope ∈ portfolio/period/trader/counterparty，软硬限分离",
    ),
    (
        "risk_alert_event",
        [
            ([("created_at", DESCENDING)], False, "idx_alert_created"),
            ([("status", ASCENDING), ("severity", ASCENDING)], False, "idx_alert_status_severity"),
            ([("snapshot_id", ASCENDING)], False, "idx_alert_snapshot"),
        ],
        "预警事件：必须可追溯到触发它的快照",
    ),
    (
        "risk_stress_scenario",
        [
            ([("scenario_id", ASCENDING)], True, "idx_stress_scenario_id"),
            ([("enabled", ASCENDING), ("category", ASCENDING)], False, "idx_stress_enabled_category"),
        ],
        "压力测试场景库：确定性情景定义，可覆盖内置默认",
    ),
    (
        "risk_counterparty",
        [
            ([("counterparty_id", ASCENDING)], True, "idx_counterparty_id"),
        ],
        "交易对手：信用评级、履约保函额度、保证金余额",
    ),
]


def init_collections() -> None:
    existing = set(DATABASE.list_collection_names())
    for name, indexes, desc in COLLECTIONS:
        if name not in existing:
            DATABASE.create_collection(name)
            logger.info("创建集合 %s —— %s", name, desc)
        else:
            logger.info("集合 %s 已存在，跳过创建", name)

        for keys, unique, idx_name in indexes:
            try:
                DATABASE[name].create_index(keys, unique=bool(unique), name=idx_name)
                logger.info("  + 索引 %s", idx_name)
            except Exception as exc:  # 索引冲突不阻断初始化
                logger.warning("  ! 索引 %s 创建失败: %s", idx_name, exc)

    logger.info("风险域集合初始化完成")


def seed_default_limits() -> None:
    """写入内置默认限额（仅当集合为空时），生产可后续按业务调整。"""
    if DATABASE.risk_limit.count_documents({}) > 0:
        logger.info("risk_limit 已有数据，跳过默认限额写入")
        return
    defaults: List[Dict[str, Any]] = [
        {"limit_id": "total-exposure", "scope": "portfolio", "limit_type": "total_price_exposure",
         "threshold": 5_000_000.0, "warn_ratio": 0.8, "enabled": True, "desc": "组合价格敞口上限(元)"},
        {"limit_id": "net-position", "scope": "portfolio", "limit_type": "net_position_mwh",
         "threshold": 5_000.0, "warn_ratio": 0.8, "enabled": True, "desc": "组合净敞口上限(MWh)"},
        {"limit_id": "max-period", "scope": "period", "limit_type": "max_period_mwh",
         "threshold": 300.0, "warn_ratio": 0.8, "enabled": True, "desc": "单时段敞口上限(MWh)"},
        {"limit_id": "portfolio-var", "scope": "portfolio", "limit_type": "var_yuan",
         "threshold": 1_000_000.0, "warn_ratio": 0.8, "enabled": True, "desc": "组合 VaR 上限(元)"},
        {"limit_id": "coverage-gap", "scope": "portfolio", "limit_type": "coverage_gap",
         "threshold": 0.3, "warn_ratio": 0.8, "enabled": True, "desc": "覆盖率缺口上限(0-1)"},
    ]
    DATABASE.risk_limit.insert_many(defaults)
    logger.info("写入 %d 条默认限额", len(defaults))


if __name__ == "__main__":
    try:
        init_collections()
        seed_default_limits()
    except Exception as exc:
        logger.error("初始化失败: %s", exc, exc_info=True)
        sys.exit(1)
