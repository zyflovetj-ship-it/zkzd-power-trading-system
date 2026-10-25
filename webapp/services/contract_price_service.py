"""
中长期合同价格分析 - 业务服务
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pymongo.database import Database

from webapp.models.contract_price import (
    DailySummaryResponse,
    DailySummaryKPIs,
    ContractTypeSummary,
    CurvePoint,
    CurveData,
    DailyCurvesResponse
)

logger = logging.getLogger(__name__)


class ContractPriceService:
    """中长期合同价格分析服务"""

    def __init__(self, db: Database):
        self.db = db
        self.contracts_collection = db["contracts_aggregated_daily"]
        self.spot_collection = db["day_ahead_spot_price"]

    def _period_to_time_str(self, period: int, total_periods: int = 48) -> str:
        """
        将时段序号转换为时间字符串（时段结束时间）
        
        Args:
            period: 时段序号 (1-based)
            total_periods: 总时段数 (24/48/96)
        
        Returns:
            时间字符串 HH:MM（代表该时段的结束时间）
        
        Examples:
            - 24点: period 1 -> 01:00, period 24 -> 24:00
            - 48点: period 1 -> 00:30, period 48 -> 24:00
            - 96点: period 1 -> 00:15, period 96 -> 24:00
        """
        if total_periods == 24:
            # 24点: 每小时一个时段
            # period 1 -> 01:00, period 24 -> 24:00
            hour = period
            minute = 0
        elif total_periods == 48:
            # 48点: 每30分钟一个时段
            # period 1 -> 00:30, period 2 -> 01:00, ..., period 48 -> 24:00
            hour = period // 2
            minute = (period % 2) * 30
            if minute == 0 and period % 2 == 0:
                minute = 0
            else:
                minute = 30 if period % 2 == 1 else 0
            # 简化计算
            total_minutes = period * 30
            hour = total_minutes // 60
            minute = total_minutes % 60
        elif total_periods == 96:
            # 96点: 每15分钟一个时段
            # period 1 -> 00:15, period 96 -> 24:00
            total_minutes = period * 15
            hour = total_minutes // 60
            minute = total_minutes % 60
        else:
            # 默认使用48点逻辑
            total_minutes = period * 30
            hour = total_minutes // 60
            minute = total_minutes % 60
        
        return f"{hour:02d}:{minute:02d}"


    def _calc_daily_stats(self, doc: dict) -> tuple:
        """
        获取日电量和日均价（直接从文档预计算字段读取）
        返回 (total_quantity, avg_price)
        """
        # 优先使用文档中的预计算字段
        total_quantity = doc.get("daily_total_quantity")
        avg_price = doc.get("daily_avg_price")
        
        if total_quantity is not None and avg_price is not None:
            return total_quantity, avg_price
        
        # 兜底：如果预计算字段不存在，从periods数组计算
        periods = doc.get("periods", [])
        if not periods:
            return 0, 0

        total_quantity = 0
        weighted_sum = 0

        for p in periods:
            qty = p.get("quantity_mwh", 0) or 0
            price = p.get("price_yuan_per_mwh", 0) or 0
            total_quantity += qty
            weighted_sum += qty * price

        avg_price = weighted_sum / total_quantity if total_quantity > 0 else 0
        return total_quantity, avg_price

    # 注：现货价格获取已迁移到通用模块 spot_price_service.py

    def get_daily_summary(self, date_str: str, entity: str = "全市场", spot_type: str = "day_ahead") -> DailySummaryResponse:
        """获取单日汇总数据
        
        Args:
            date_str: 日期字符串 YYYY-MM-DD
            entity: 实体名称
            spot_type: 现货类型 day_ahead(日前) 或 real_time(实时)
        """
        logger.info(f"[START] get_daily_summary: date={date_str}, entity={entity}, spot_type={spot_type}")

        # 查询所有合同数据
        logger.info("[STEP 1] 查询合同数据...")
        cursor = self.contracts_collection.find({
            "date": date_str,
            "entity": entity
        })
        docs = list(cursor)
        logger.info(f"[STEP 1] 完成，找到 {len(docs)} 条记录")

        # 调试日志：打印所有查询到的记录的类型和周期
        for doc in docs:
            ct = doc.get("contract_type", "")
            cp = doc.get("contract_period", "")
            logger.info(f"  - contract_type={ct}, contract_period={cp}")



        if not docs:
            # 返回空数据
            return DailySummaryResponse(
                date=date_str,
                kpis=DailySummaryKPIs(
                    total_quantity=0,
                    overall_avg_price=0,
                    price_range_min=0,
                    price_range_max=0,
                    yearly_ratio=0,
                    monthly_ratio=0,
                    within_month_ratio=0
                ),
                contract_curves=[],
                spot_curves=[],
                type_summary=[]
            )

        # 分离整体数据和明细数据
        # 整体数据用于汇总指标和价格曲线
        # 明细数据用于表格（排除所有type或period为"整体"的记录）
        overall_doc = None
        detail_docs = []
        for doc in docs:
            contract_type = doc.get("contract_type", "")
            contract_period = doc.get("contract_period", "")

            # 整体+整体用于汇总指标
            if contract_type == "整体" and contract_period == "整体":
                overall_doc = doc
            # 排除任何维度为"整体"的记录，只保留具体明细
            elif contract_type != "整体" and contract_period != "整体":
                detail_docs.append(doc)


        # 计算汇总指标（从 periods 数组计算）
        if overall_doc:
            total_quantity, overall_avg_price = self._calc_daily_stats(overall_doc)
        else:
            total_quantity, overall_avg_price = 0, 0

        # 计算价格区间
        all_prices = []
        if overall_doc and overall_doc.get("periods"):
            for p in overall_doc["periods"]:
                if p.get("price_yuan_per_mwh") is not None:
                    all_prices.append(p["price_yuan_per_mwh"])

        price_range_min = min(all_prices) if all_prices else 0
        price_range_max = max(all_prices) if all_prices else 0

        # 计算各周期占比和均价
        # 优先从 contract_type="整体" 下的各周期文档获取电量
        period_stats = {"年度": {"quantity": 0, "price": None}, 
                       "月度": {"quantity": 0, "price": None}, 
                       "月内": {"quantity": 0, "price": None}}

        # 方案1：从整体类型下的周期文档获取
        for doc in docs:
            if doc.get("contract_type") == "整体" and doc.get("contract_period") in period_stats:
                period = doc.get("contract_period")
                doc_qty, doc_price = self._calc_daily_stats(doc)
                period_stats[period]["quantity"] = doc_qty
                period_stats[period]["price"] = doc_price if doc_price > 0 else None

        # 方案2：如果整体类型下无数据，则从具体类型累加
        for period in period_stats:
            if period_stats[period]["quantity"] == 0:
                for doc in detail_docs:
                    if doc.get("contract_period") == period:
                        doc_qty, doc_price = self._calc_daily_stats(doc)
                        period_stats[period]["quantity"] += doc_qty

        # 计算占比
        yearly_ratio = (period_stats["年度"]["quantity"] / total_quantity * 100) if total_quantity > 0 else 0
        monthly_ratio = (period_stats["月度"]["quantity"] / total_quantity * 100) if total_quantity > 0 else 0
        within_month_ratio = (period_stats["月内"]["quantity"] / total_quantity * 100) if total_quantity > 0 else 0

        kpis = DailySummaryKPIs(
            total_quantity=round(total_quantity, 2),
            overall_avg_price=round(overall_avg_price, 2),
            price_range_min=round(price_range_min, 2),
            price_range_max=round(price_range_max, 2),
            yearly_ratio=round(yearly_ratio, 1),
            monthly_ratio=round(monthly_ratio, 1),
            within_month_ratio=round(within_month_ratio, 1),
            yearly_avg_price=period_stats["年度"]["price"],
            monthly_avg_price=period_stats["月度"]["price"],
            within_month_avg_price=period_stats["月内"]["price"]
        )

        # 构建整体价格曲线
        contract_curves = []
        if overall_doc and overall_doc.get("periods"):
            # 确定时段总数用于计算时间字符串
            total_periods = len(overall_doc["periods"])
            for p in overall_doc["periods"]:
                period = p.get("period", 0)
                price = p.get("price_yuan_per_mwh")
                quantity = p.get("quantity_mwh")
                if period and price is not None:
                    contract_curves.append(CurvePoint(
                        period=period,
                        time_str=self._period_to_time_str(period, total_periods),
                        price=round(price, 2),
                        quantity=round(quantity, 2) if quantity else None
                    ))
        contract_curves.sort(key=lambda x: x.period)
        logger.info(f"[STEP 3] 构建合同曲线完成，共 {len(contract_curves)} 个点")

        # 根据中长期合同数据的点数动态确定现货价格分辨率
        # 9月以前的中长期合同是24点，之后的是48点，未来可能是96点
        contract_point_count = len(contract_curves)
        if contract_point_count <= 24:
            spot_resolution = 24
        elif contract_point_count <= 48:
            spot_resolution = 48
        else:
            spot_resolution = 96
        
        logger.info(f"[STEP 4] 获取现货价格... (分辨率: {spot_resolution}点，适配中长期{contract_point_count}点，类型: {spot_type})")
        from webapp.services.spot_price_service import get_spot_prices
        # 包含电量数据用于计算仓位占比
        spot_data = get_spot_prices(self.db, date_str, data_type=spot_type, resolution=spot_resolution, include_volume=True)
        spot_curves = [
            CurvePoint(
                period=p.period,
                time_str=p.time_str,
                price=p.price,
                quantity=p.volume  # 日前出清电量
            )
            for p in spot_data.points
            if p.price is not None
        ]
        logger.info(f"[STEP 4] 获取现货价格完成，共 {len(spot_curves)} 个点")





        # 构建明细表格
        type_summary = []
        for doc in detail_docs:
            # 计算峰谷差
            prices = []
            if doc.get("periods"):
                for p in doc["periods"]:
                    if p.get("price_yuan_per_mwh") is not None:
                        prices.append(p["price_yuan_per_mwh"])

            max_price = max(prices) if prices else None
            min_price = min(prices) if prices else None
            peak_valley = (max_price - min_price) if (max_price and min_price) else None

            # 从 periods 数组计算日电量和均价
            doc_qty, doc_price = self._calc_daily_stats(doc)

            type_summary.append(ContractTypeSummary(
                contract_type=doc.get("contract_type", ""),
                contract_period=doc.get("contract_period", ""),
                daily_total_quantity=round(doc_qty, 2),
                daily_avg_price=round(doc_price, 2),
                max_price=round(max_price, 2) if max_price else None,
                min_price=round(min_price, 2) if min_price else None,
                peak_valley_spread=round(peak_valley, 2) if peak_valley else None
            ))

        # 按类型和周期排序
        type_order = {"市场化": 0, "绿电": 1, "代理购电": 2, "整体": 3}
        period_order = {"年度": 0, "月度": 1, "月内": 2, "整体": 3}

        type_summary.sort(key=lambda x: (type_order.get(x.contract_type, 99), 
                                         period_order.get(x.contract_period, 99)))

        # 构建按合同类型的曲线数据
        # 查找每个合同类型+整体周期的记录
        curves_by_type = {}
        contract_types_to_find = ["整体", "市场化", "绿电", "代理购电"]
        for target_type in contract_types_to_find:
            for doc in docs:
                if doc.get("contract_type") == target_type and doc.get("contract_period") == "整体":
                    curve_points = []
                    if doc.get("periods"):
                        doc_total_periods = len(doc["periods"])
                        for p in doc["periods"]:
                            period = p.get("period", 0)
                            price = p.get("price_yuan_per_mwh")
                            quantity = p.get("quantity_mwh")
                            if period and price is not None:
                                curve_points.append({
                                    "period": period,
                                    "time_str": self._period_to_time_str(period, doc_total_periods),
                                    "price": round(price, 2),
                                    "quantity": round(quantity, 2) if quantity else None
                                })
                        curve_points.sort(key=lambda x: x["period"])
                    curves_by_type[target_type] = curve_points
                    break


        logger.info(f"[STEP 5] 构建curves_by_type完成，类型数: {len(curves_by_type)}")

        # 构建按"类型-周期"组合的曲线数据
        # 可选曲线: 市场化-整体/年度/月度/月内, 绿电-整体/年度/月度/月内, 代购电-整体/年度/月度
        curves_by_period = {}
        combinations = [
            ("市场化", "整体"), ("市场化", "年度"), ("市场化", "月度"), ("市场化", "月内"),
            ("绿电", "整体"), ("绿电", "年度"), ("绿电", "月度"), ("绿电", "月内"),
            ("代理购电", "整体"), ("代理购电", "年度"), ("代理购电", "月度")
        ]


        for contract_type, contract_period in combinations:
            for doc in docs:
                if doc.get("contract_type") == contract_type and doc.get("contract_period") == contract_period:
                    curve_points = []
                    if doc.get("periods"):
                        doc_total_periods = len(doc["periods"])
                        for p in doc["periods"]:
                            period = p.get("period", 0)
                            price = p.get("price_yuan_per_mwh")
                            quantity = p.get("quantity_mwh")
                            if period and price is not None:
                                curve_points.append({
                                    "period": period,
                                    "time_str": self._period_to_time_str(period, doc_total_periods),
                                    "price": round(price, 2),
                                    "quantity": round(quantity, 2) if quantity else None
                                })
                        curve_points.sort(key=lambda x: x["period"])
                    # 使用组合键名
                    key = f"{contract_type}-{contract_period}"
                    curves_by_period[key] = curve_points
                    break

        logger.info(f"[STEP 6] 构建curves_by_period(组合)完成，组合数: {len(curves_by_period)}")

        return DailySummaryResponse(
            date=date_str,
            kpis=kpis,
            contract_curves=contract_curves,
            spot_curves=spot_curves,
            type_summary=type_summary,
            curves_by_type=curves_by_type,
            curves_by_period=curves_by_period
        )



