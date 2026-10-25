"""
现货价格数据服务 - 通用模块

提供日前和实时现货价格数据的统一获取接口，支持多种时间粒度输出。
"""
import logging
from typing import List, Dict, Tuple, Literal, Optional
from datetime import datetime
from dataclasses import dataclass, field
from pymongo.database import Database

logger = logging.getLogger(__name__)


@dataclass
class SpotDataPoint:
    """现货数据点"""
    period: int  # 时段序号
    time_str: str  # 时间字符串 HH:MM
    price: Optional[float] = None  # 价格 (元/MWh)
    volume: Optional[float] = None  # 电量 (MWh)


@dataclass
class SpotCurveData:
    """现货曲线数据"""
    date: str  # 日期 YYYY-MM-DD
    data_type: str  # 数据类型: "day_ahead" 或 "real_time"
    resolution: int  # 时间分辨率: 24, 48, 96
    points: List[SpotDataPoint] = field(default_factory=list)


# 时间分辨率类型
Resolution = Literal[24, 48, 96]


def get_spot_prices(
    db: Database,
    date_str: str,
    data_type: Literal["day_ahead", "real_time"] = "day_ahead",
    resolution: Resolution = 48,
    include_volume: bool = True
) -> SpotCurveData:
    """
    获取现货价格曲线数据
    
    Args:
        db: MongoDB数据库实例
        date_str: 日期字符串 YYYY-MM-DD
        data_type: 数据类型，"day_ahead" 日前 或 "real_time" 实时
        resolution: 输出时间分辨率，24点/48点/96点
        include_volume: 是否包含电量数据
    
    Returns:
        SpotCurveData: 包含曲线数据点的结构
    """
    # 选择数据集合
    collection_name = "day_ahead_spot_price" if data_type == "day_ahead" else "real_time_spot_price"
    collection = db[collection_name]
    
    # 查询字段
    projection = {"_id": 0, "time_str": 1, "avg_clearing_price": 1}
    if include_volume:
        projection["total_clearing_power"] = 1
    
    # 查询数据
    cursor = collection.find(
        {"date_str": date_str},
        projection
    ).sort("time_str", 1)
    
    raw_docs = list(cursor)
    
    if not raw_docs:
        logger.warning(f"未找到日期 {date_str} 的 {data_type} 现货数据")
        return SpotCurveData(
            date=date_str,
            data_type=data_type,
            resolution=resolution,
            points=[]
        )
    
    logger.info(f"获取 {date_str} {data_type} 现货数据: {len(raw_docs)} 条原始记录")
    
    # 按时间分辨率聚合
    if resolution == 96:
        # 96点: 15分钟间隔，直接使用原始数据
        points = _to_96_points(raw_docs, include_volume)
    elif resolution == 48:
        # 48点: 30分钟间隔，每2个15分钟聚合为1个
        points = _to_48_points(raw_docs, include_volume)
    elif resolution == 24:
        # 24点: 60分钟间隔，每4个15分钟聚合为1个
        points = _to_24_points(raw_docs, include_volume)
    else:
        raise ValueError(f"不支持的时间分辨率: {resolution}")
    
    return SpotCurveData(
        date=date_str,
        data_type=data_type,
        resolution=resolution,
        points=points
    )


def _to_96_points(docs: List[dict], include_volume: bool) -> List[SpotDataPoint]:
    """转换为96点数据（15分钟间隔）"""
    points = []
    for i, doc in enumerate(docs):
        time_str = doc.get("time_str", "")
        price = doc.get("avg_clearing_price")
        volume = doc.get("total_clearing_power") if include_volume else None
        
        points.append(SpotDataPoint(
            period=i + 1,
            time_str=time_str,
            price=round(price, 2) if price is not None else None,
            volume=round(volume, 2) if volume is not None else None
        ))
    
    return points


def _to_48_points(docs: List[dict], include_volume: bool) -> List[SpotDataPoint]:
    """转换为48点数据（30分钟间隔）"""
    # 按30分钟时段分组
    period_data: Dict[int, Dict[str, List[float]]] = {}
    
    for doc in docs:
        time_str = doc.get("time_str", "")
        price = doc.get("avg_clearing_price")
        volume = doc.get("total_clearing_power")
        
        parts = time_str.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            
            # 计算属于哪个30分钟时段 (1-48)
            # 00:00-00:29 -> 时段1, 00:30-00:59 -> 时段2, ...
            period = hour * 2 + (1 if minute < 30 else 2)
            
            if period not in period_data:
                period_data[period] = {"prices": [], "volumes": []}
            
            if price is not None:
                period_data[period]["prices"].append(price)
            if volume is not None:
                period_data[period]["volumes"].append(volume)
    
    # 计算每个时段的平均值
    points = []
    for period in range(1, 49):
        if period in period_data and period_data[period]["prices"]:
            data = period_data[period]
            avg_price = sum(data["prices"]) / len(data["prices"])
            sum_volume = sum(data["volumes"]) if data["volumes"] else None
            
            # 计算时间字符串（时段结束时间）
            # period 1 -> 00:30, period 48 -> 24:00
            total_minutes = period * 30
            hour = total_minutes // 60
            minute = total_minutes % 60
            time_str = f"{hour:02d}:{minute:02d}"
            
            points.append(SpotDataPoint(
                period=period,
                time_str=time_str,
                price=round(avg_price, 2),
                volume=round(sum_volume, 2) if sum_volume is not None else None
            ))
    
    return points


def _to_24_points(docs: List[dict], include_volume: bool) -> List[SpotDataPoint]:
    """转换为24点数据（60分钟间隔）"""
    # 按小时分组
    period_data: Dict[int, Dict[str, List[float]]] = {}
    
    for doc in docs:
        time_str = doc.get("time_str", "")
        price = doc.get("avg_clearing_price")
        volume = doc.get("total_clearing_power")
        
        parts = time_str.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            
            # 计算属于哪个小时时段 (1-24)
            # 特殊处理: 24:00 属于第24个时段
            if hour == 24 or (hour == 0 and time_str == "24:00"):
                period = 24
            else:
                period = hour + 1
            
            if period not in period_data:
                period_data[period] = {"prices": [], "volumes": []}
            
            if price is not None:
                period_data[period]["prices"].append(price)
            if volume is not None:
                period_data[period]["volumes"].append(volume)
    
    # 计算每个时段的平均值
    points = []
    for period in range(1, 25):
        if period in period_data and period_data[period]["prices"]:
            data = period_data[period]
            avg_price = sum(data["prices"]) / len(data["prices"])
            sum_volume = sum(data["volumes"]) if data["volumes"] else None
            
            # 时间字符串为该小时的结束时间
            # period 1 -> 01:00, period 24 -> 24:00
            hour = period
            time_str = f"{hour:02d}:00"
            
            points.append(SpotDataPoint(
                period=period,
                time_str=time_str,
                price=round(avg_price, 2),
                volume=round(sum_volume, 2) if sum_volume is not None else None
            ))
    
    return points


def get_spot_prices_dict(
    db: Database,
    date_str: str,
    data_type: Literal["day_ahead", "real_time"] = "day_ahead",
    resolution: Resolution = 48,
    include_volume: bool = True
) -> List[dict]:
    """
    获取现货价格曲线数据（字典格式，便于JSON序列化）
    
    返回格式: [{"period": 1, "time_str": "00:00", "price": 350.5, "volume": 1000}, ...]
    """
    curve_data = get_spot_prices(db, date_str, data_type, resolution, include_volume)
    
    return [
        {
            "period": p.period,
            "time_str": p.time_str,
            "price": p.price,
            "volume": p.volume
        }
        for p in curve_data.points
    ]
