import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import statistics
from collections import defaultdict

from pymongo.database import Database
from pymongo import ASCENDING
from webapp.services.tou_service import get_tou_rule_by_date

# 导入模型 (虽然 Service 层主要返回 Dict，但类型提示可以使用)
# from webapp.models.trend_analysis import ... 

logger = logging.getLogger(__name__)

class TrendAnalysisService:
    """
    现货趋势分析服务层
    
    职责：
    - 提供价格趋势、星期特性、波动性、套利机会、异常分析等业务逻辑
    - 封装数据库聚合查询
    """

    def __init__(self, db: Database) -> None:
        """
        初始化服务
        
        Args:
            db: MongoDB 数据库实例
        """
        self.db = db
        self.da_collection = self.db['day_ahead_spot_price']
        self.rt_collection = self.db['real_time_spot_price']
        self.tou_collection = self.db['tou_rules']
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """确保数据库索引存在"""
        try:
            # 确保 date_str 索引存在，用于范围查询
            for col in [self.da_collection, self.rt_collection]:
                indexes = [
                    ([('date_str', 1)], {'name': 'idx_date_str'}),
                ]
                
                # 获取现有索引信息
                existing_indexes = list(col.list_indexes())
                existing_names = {idx.get('name') for idx in existing_indexes}
                # 将 SON 对象转换为 tuple 以便比较: (('datetime', 1),)
                existing_keys = {tuple(idx.get('key').items()) for idx in existing_indexes}

                for keys, options in indexes:
                    key_tuple = tuple(keys)
                    
                    # 1. 如果键已经存在索引（无论名字叫什么），则跳过，避免 IndexOptionsConflict
                    if key_tuple in existing_keys:
                        continue
                        
                    # 2. 如果名字不存在，则尝试创建
                    if options['name'] not in existing_names:
                        try:
                            col.create_index(keys, **options)
                            logger.info(f"创建索引: {options['name']} on {col.name}")
                        except Exception as e:
                            logger.warning(f"创建索引 {options['name']} 失败: {str(e)}")
        except Exception as e:
            logger.warning(f"创建索引时出错: {str(e)}")

    # ========== 核心业务方法 ==========

    def get_price_trend(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        """
        需求1：价格趋势分析

        Args:
            start_date_str: 开始日期字符串 YYYY-MM-DD
            end_date_str: 结束日期字符串 YYYY-MM-DD

        Returns:
            Dict 包含 daily_trends 和 period_trends
        """
        # 1. 生成日期列表
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

        # 2. 获取基础数据
        query = {"date_str": {"$in": date_list}}
        da_docs = list(self.da_collection.find(query).sort("date_str", 1))
        rt_docs = list(self.rt_collection.find(query).sort("date_str", 1))

        # 3. 获取分时电价规则 (简化处理：假设规则在查询期内不变，取 start_date 的规则)
        tou_rules = self._get_tou_rules(start_date_str)
        
        # 4. 聚合计算
        daily_stats = defaultdict(lambda: {
            "da_vol": 0, "da_cost": 0, "da_prices": [],
            "rt_vol": 0, "rt_cost": 0, "rt_prices": []
        })

        period_stats = defaultdict(lambda: defaultdict(lambda: {
            "vol": 0, "cost": 0
        })) # date -> period_type -> {vol, cost}

        # 用于计算全量价差: (date_str, time_str) -> {da, rt}
        detailed_prices = defaultdict(lambda: {"da": None, "rt": None})

        # 处理日前数据
        for doc in da_docs:
            date_str = doc.get('date_str')
            time_str = doc.get('time_str')
            if not date_str or not time_str:
                continue

            price = doc.get('avg_clearing_price')
            vol = doc.get('total_clearing_power', 0)

            if price is not None:
                daily_stats[date_str]["da_vol"] += vol
                daily_stats[date_str]["da_cost"] += price * vol
                daily_stats[date_str]["da_prices"].append(price)
                detailed_prices[(date_str, time_str)]["da"] = price

        # 处理实时数据
        for doc in rt_docs:
            date_str = doc.get('date_str')
            time_str = doc.get('time_str')
            if not date_str or not time_str:
                continue

            price = doc.get('avg_clearing_price')
            vol = doc.get('total_clearing_power', 0)

            if price is not None:
                daily_stats[date_str]["rt_vol"] += vol
                daily_stats[date_str]["rt_cost"] += price * vol
                daily_stats[date_str]["rt_prices"].append(price)
                detailed_prices[(date_str, time_str)]["rt"] = price

                # 分时段统计 (RT)
                # 使用 time_str 查找规则
                period_type = tou_rules.get(time_str, "平段")
                # 如果没找到，尝试去零 (e.g. 00:15 -> 0:15) 再次查找
                if period_type == "平段" and time_str.startswith("0"):
                    short_key = f"{int(time_str.split(':')[0])}:{time_str.split(':')[1]}"
                    period_type = tou_rules.get(short_key, "平段")

                period_stats[date_str][period_type]["vol"] += vol
                period_stats[date_str][period_type]["cost"] += price * vol

        # DEBUG LOGGING
        logger.info(f"TrendAnalysis: Date Range {start_date_str} - {end_date_str}")
        logger.info(f"TrendAnalysis: Found {len(da_docs)} DA docs, {len(rt_docs)} RT docs")
        logger.info(f"TrendAnalysis: detailed_prices keys count: {len(detailed_prices)}")
        
        # 4. 统计每日正负价差时段数
        daily_spread_counts = defaultdict(lambda: {"pos": 0, "neg": 0})
        for key, prices in detailed_prices.items():
            date_s = key[0]
            if prices["da"] is not None and prices["rt"] is not None:
                spread = prices["rt"] - prices["da"]
                if spread > 0:
                    daily_spread_counts[date_s]["pos"] += 1
                elif spread < 0:
                    daily_spread_counts[date_s]["neg"] += 1

        # 5. 格式化输出 daily_trends
        daily_trends = []
        sorted_dates = sorted(daily_stats.keys())
        
        for date_str in sorted_dates:
            stat = daily_stats[date_str]
            
            vwap_da = stat["da_cost"] / stat["da_vol"] if stat["da_vol"] > 0 else None
            vwap_rt = stat["rt_cost"] / stat["rt_vol"] if stat["rt_vol"] > 0 else None
            twap_da = statistics.mean(stat["da_prices"]) if stat["da_prices"] else None
            twap_rt = statistics.mean(stat["rt_prices"]) if stat["rt_prices"] else None
            
            daily_trends.append({
                "date": date_str,
                "vwap_da": round(vwap_da, 2) if vwap_da is not None else None,
                "vwap_rt": round(vwap_rt, 2) if vwap_rt is not None else None,
                "vwap_spread": round(vwap_rt - vwap_da, 2) if (vwap_rt is not None and vwap_da is not None) else None,
                "twap_da": round(twap_da, 2) if twap_da is not None else None,
                "twap_rt": round(twap_rt, 2) if twap_rt is not None else None,
                "twap_spread": round(twap_rt - twap_da, 2) if (twap_rt is not None and twap_da is not None) else None,
                "positive_spread_count": daily_spread_counts[date_str]["pos"],
                "negative_spread_count": daily_spread_counts[date_str]["neg"]
            })
            
        period_trends_output = defaultdict(list)
        for date_str in sorted_dates:
            p_stat = period_stats[date_str]
            for p_type, val in p_stat.items():
                vwap = val["cost"] / val["vol"] if val["vol"] > 0 else None
                period_trends_output[p_type].append({
                    "date": date_str,
                    "period_type": p_type,
                    "vwap": round(vwap, 2) if vwap is not None else None
                })

        # 计算全量价差
        all_spreads = []
        # 按日期和时间排序
        sorted_keys = sorted(detailed_prices.keys())
        for key in sorted_keys:
            prices = detailed_prices[key]
            if prices["da"] is not None and prices["rt"] is not None:
                all_spreads.append(round(prices["rt"] - prices["da"], 2))

        # 计算价差统计指标
        spread_stats = {
            "avgSpread": 0,
            "positiveSpreadRatio": 0,
            "negativeSpreadRatio": 0,
            "maxSpread": 0,
            "minSpread": 0
        }
        
        if all_spreads:
            spread_stats["avgSpread"] = round(statistics.mean(all_spreads), 2)
            spread_stats["maxSpread"] = max(all_spreads)
            spread_stats["minSpread"] = min(all_spreads)
            
            positive_count = sum(1 for s in all_spreads if s > 0)
            negative_count = sum(1 for s in all_spreads if s < 0)
            total_count = len(all_spreads)
            
            spread_stats["positiveSpreadRatio"] = round((positive_count / total_count) * 100, 1)
            spread_stats["negativeSpreadRatio"] = round((negative_count / total_count) * 100, 1)

        # 计算价差分布直方图
        spread_distribution = []
        if all_spreads:
            step = 50
            min_val = int(spread_stats["minSpread"] // step * step)
            max_val = int(spread_stats["maxSpread"] // step * step + step) # +step to include max value range
            
            # 初始化桶
            buckets = defaultdict(int)
            # 预填充所有区间为0，保证连续性
            for i in range(min_val, max_val, step):
                label = f"{i}~{i + step}"
                buckets[label] = 0
                
            for s in all_spreads:
                bucket_start = int(s // step * step)
                label = f"{bucket_start}~{bucket_start + step}"
                buckets[label] += 1
                
            # 转换为列表并排序 (按区间数值排序)
            # 解析 label 的起始值进行排序
            sorted_buckets = sorted(buckets.items(), key=lambda x: int(x[0].split('~')[0]))
            
            spread_distribution = [{"range": k, "count": v} for k, v in sorted_buckets]

        return {
            "daily_trends": daily_trends,
            "period_trends": period_trends_output,
            "spread_stats": spread_stats,
            "spread_distribution": spread_distribution
        }

    def get_weekday_analysis(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        """
        需求2：星期特性分析
        """
        # 生成日期列表
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

        query = {"date_str": {"$in": date_list}}
        rt_docs = list(self.rt_collection.find(query))
        
        # 按星期分组收集日均VWAP
        weekday_data = defaultdict(lambda: {
            "daily_vwaps": [], # 存储每一天的 VWAP
            "temp_daily": defaultdict(lambda: {"cost": 0, "vol": 0}) # 临时存储当天的累加
        })

        # 1. 遍历数据，累加每天的 cost 和 vol
        for doc in rt_docs:
            date_str = doc.get('date_str')
            if not date_str:
                continue

            # 从 date_str 解析出星期几：0=Mon, 6=Sun
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = dt.weekday()
            
            price = doc.get('avg_clearing_price')
            vol = doc.get('total_clearing_power', 0)
            
            if price is not None:
                weekday_data[weekday]["temp_daily"][date_str]["cost"] += price * vol
                weekday_data[weekday]["temp_daily"][date_str]["vol"] += vol
                
        # 2. 计算每天的 VWAP 并存入列表
        weekday_stats_list = []
        weekdays_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        
        for wd in range(7):
            data = weekday_data[wd]
            vwaps = []
            for date_str, val in data["temp_daily"].items():
                if val["vol"] > 0:
                    vwaps.append(val["cost"] / val["vol"])
            
            if not vwaps:
                stats = {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0}
                outliers = []
            else:
                vwaps.sort()
                q1 = statistics.quantiles(vwaps, n=4)[0] if len(vwaps) >= 2 else vwaps[0]
                median = statistics.median(vwaps)
                q3 = statistics.quantiles(vwaps, n=4)[2] if len(vwaps) >= 2 else vwaps[-1]
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                # 过滤离群值用于箱线图绘制（通常箱线图本身包含离群值点，这里简单处理）
                valid_values = [v for v in vwaps if lower_bound <= v <= upper_bound]
                outliers = [v for v in vwaps if v < lower_bound or v > upper_bound]
                
                stats = {
                    "min": min(valid_values) if valid_values else min(vwaps),
                    "q1": q1,
                    "median": median,
                    "q3": q3,
                    "max": max(valid_values) if valid_values else max(vwaps)
                }
            
            weekday_stats_list.append({
                "weekday": wd,
                "weekday_name": weekdays_map[wd],
                "stats": stats,
                "outliers": outliers
            })
            
        return {"distribution": weekday_stats_list, "heatmap_data": []}

    def get_volatility_analysis(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        """
        需求3：波动性分析
        """
        # 生成日期列表
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

        query = {"date_str": {"$in": date_list}}
        rt_docs = list(self.rt_collection.find(query).sort("date_str", 1))
        
        # 按天分组
        daily_data = defaultdict(list)
        for doc in rt_docs:
            date_str = doc.get('date_str')
            if date_str:
                daily_data[date_str].append(doc)
                
        result = []
        for date_str, docs in daily_data.items():
            prices = [d.get('avg_clearing_price') for d in docs if d.get('avg_clearing_price') is not None]
            
            if not prices or len(prices) < 2:
                continue
                
            # 1. CV (变异系数)
            mean_price = statistics.mean(prices)
            std_price = statistics.stdev(prices)
            cv = std_price / mean_price if mean_price != 0 else 0
            
            # 2. 最大爬坡
            max_ramp = 0
            for i in range(1, len(prices)):
                ramp = abs(prices[i] - prices[i-1])
                if ramp > max_ramp:
                    max_ramp = ramp
                    
            result.append({
                "date": date_str,
                "cv_rt": round(cv, 4),
                "max_ramp": round(max_ramp, 2),
                "spread_std": 0 # 暂未计算价差标准差，需关联 DA 数据
            })
            
        return {"daily_volatility": sorted(result, key=lambda x: x['date'])}

    def get_arbitrage_analysis(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        """
        需求4：储能套利机会分析
        """
        # 生成日期列表
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

        query = {"date_str": {"$in": date_list}}
        rt_docs = list(self.rt_collection.find(query).sort("date_str", 1))
        
        daily_data = defaultdict(list)
        for doc in rt_docs:
            date_str = doc.get('date_str')
            if date_str:
                daily_data[date_str].append(doc)
                
        daily_arbitrage = []
        total_max_spread = 0
        
        for date_str, docs in daily_data.items():
            # 提取价格和时间
            points = []
            for doc in docs:
                price = doc.get('avg_clearing_price')
                time_str = doc.get('time_str')
                if price is not None and time_str:
                    points.append({"price": price, "time": time_str})
            
            if not points: continue
            
            # 算法：寻找最大价差 (先买后卖)
            # O(N) 算法：维护当前最低价
            min_price = float('inf')
            min_price_time = ""
            max_spread = float('-inf')
            best_buy_time = ""
            best_sell_time = ""
            best_buy_price = 0
            best_sell_price = 0
            
            # 简单起见，这里使用 O(N^2) 或者简单的双指针，由于 N=96 很小，O(N^2) 也无所谓
            # 但为了性能，使用 O(N)
            # 记录当前遇到的最低价及其时间
            curr_min_price = points[0]["price"]
            curr_min_time = points[0]["time"]
            
            for i in range(1, len(points)):
                sell_price = points[i]["price"]
                sell_time = points[i]["time"]
                
                # 计算如果现在卖出的价差
                spread = sell_price - curr_min_price
                
                if spread > max_spread:
                    max_spread = spread
                    best_buy_price = curr_min_price
                    best_buy_time = curr_min_time
                    best_sell_price = sell_price
                    best_sell_time = sell_time
                
                # 更新最低价
                if points[i]["price"] < curr_min_price:
                    curr_min_price = points[i]["price"]
                    curr_min_time = points[i]["time"]
            
            if max_spread == float('-inf'):
                max_spread = 0
                
            # 判断时段 (简单判断：买入时间在12:00前为上午)
            period_type = "上午" if best_buy_time < "12:00" else "下午"
            
            daily_arbitrage.append({
                "date": date_str,
                "max_spread": round(max_spread, 2),
                "best_strategy": f"{best_buy_time}买入 -> {best_sell_time}卖出",
                "buy_price": best_buy_price,
                "buy_time": best_buy_time,
                "sell_price": best_sell_price,
                "sell_time": best_sell_time,
                "period_type": period_type
            })
            total_max_spread += max_spread

        avg_max_spread = total_max_spread / len(daily_arbitrage) if daily_arbitrage else 0
        
        return {
            "daily_arbitrage": sorted(daily_arbitrage, key=lambda x: x['date']),
            "summary": {
                "avg_max_spread": round(avg_max_spread, 2),
                "days_count": len(daily_arbitrage)
            }
        }

    def get_anomaly_analysis(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        """
        需求5：价格异常与极值分析
        """
        # 生成日期列表
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

        query = {"date_str": {"$in": date_list}}
        rt_docs = list(self.rt_collection.find(query).sort("date_str", 1))
        
        # 统计变量
        neg_price_count = 0
        neg_price_days = set()
        zero_price_count = 0
        zero_price_days = set()
        high_price_count = 0 # > 1000
        high_price_days = set()
        
        daily_extremums = []
        
        # 按天分组
        daily_data = defaultdict(list)
        for doc in rt_docs:
            date_str = doc.get('date_str')
            if date_str:
                daily_data[date_str].append(doc)
        
        for date_str, docs in daily_data.items():
            prices = []
            times = []
            for doc in docs:
                p = doc.get('avg_clearing_price')
                t = doc.get('time_str')
                if p is not None:
                    prices.append(p)
                    times.append(t)
                    
                    # 异常统计
                    if p < 0:
                        neg_price_count += 1
                        neg_price_days.add(date_str)
                    elif p == 0:
                        zero_price_count += 1
                        zero_price_days.add(date_str)
                    elif p > 1000:
                        high_price_count += 1
                        high_price_days.add(date_str)
            
            if not prices: continue
            
            max_p = max(prices)
            min_p = min(prices)
            max_t = times[prices.index(max_p)]
            min_t = times[prices.index(min_p)]
            
            daily_extremums.append({
                "date": date_str,
                "max_price": max_p,
                "max_time": max_t,
                "min_price": min_p,
                "min_time": min_t,
                "range_value": max_p - min_p
            })
            
        events = {
            "negative_price": {
                "event_type": "negative_price",
                "count": neg_price_count,
                "days": len(neg_price_days)
            },
            "zero_price": {
                "event_type": "zero_price",
                "count": zero_price_count,
                "days": len(zero_price_days)
            },
            "high_price": {
                "event_type": "high_price",
                "count": high_price_count,
                "days": len(high_price_days)
            }
        }
        
        return {
            "events": events,
            "daily_extremums": sorted(daily_extremums, key=lambda x: x['date']),
            "risk_timeslots": [] # 暂未实现热力图统计
        }

    def get_timeslot_stats(self, start_date_str: str, end_date_str: str) -> Dict[str, Any]:
        """
        需求6: 时段分析 - 将96个数据点聚合为48个时段并计算统计指标

        Args:
            start_date_str: 开始日期字符串 YYYY-MM-DD
            end_date_str: 结束日期字符串 YYYY-MM-DD

        Returns:
            Dict 包含 kpis, timeslot_stats, box_plot_data
        """
        # 1. 生成日期列表
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        date_list = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

        # 2. 查询数据
        query = {"date_str": {"$in": date_list}}
        da_docs = list(self.da_collection.find(query).sort("date_str", 1))
        rt_docs = list(self.rt_collection.find(query).sort("date_str", 1))

        logger.info(f"TimeSlotAnalysis: Found {len(da_docs)} DA docs, {len(rt_docs)} RT docs")

        # 3. 构建时段映射: (date_str, timeslot) -> {da_prices: [], rt_prices: [], spreads: []}
        timeslot_data = defaultdict(lambda: {
            "da_prices": [],
            "rt_prices": [],
            "spreads": []
        })

        # 辅助函数: 将 time_str 映射到48时段
        def get_timeslot_from_time_str(time_str: str) -> Tuple[int, str]:
            """将 time_str (如 "00:00", "00:15", ..., "24:00") 映射到时段编号和时间标签"""
            # 处理24:00的特殊情况
            if time_str == "24:00":
                return 48, "23:30-24:00"

            # 解析时间
            hour = int(time_str.split(":")[0])
            minute = int(time_str.split(":")[1])

            # 计算period编号 (1-96)
            period = (hour * 60 + minute) // 15
            if period == 0:
                period = 96

            # 计算时段编号 (1-48)
            timeslot = (period - 1) // 2 + 1

            # 计算时间标签
            slot_start_minutes = (timeslot - 1) * 30
            start_hour = slot_start_minutes // 60
            start_minute = slot_start_minutes % 60
            end_minutes = slot_start_minutes + 30
            end_hour = end_minutes // 60
            end_minute = end_minutes % 60

            if end_hour == 24:
                time_label = f"{start_hour:02d}:{start_minute:02d}-24:00"
            else:
                time_label = f"{start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d}"

            return timeslot, time_label

        # 4. 处理日前数据
        da_map = {}  # (date_str, timeslot) -> price
        for doc in da_docs:
            date_str = doc.get('date_str')
            time_str = doc.get('time_str')
            if not date_str or not time_str:
                continue

            price = doc.get('avg_clearing_price')
            if price is not None:
                timeslot, _ = get_timeslot_from_time_str(time_str)
                key = (date_str, timeslot)
                da_map[key] = price
                timeslot_data[timeslot]["da_prices"].append(price)

        # 5. 处理实时数据
        rt_map = {}  # (date_str, timeslot) -> price
        for doc in rt_docs:
            date_str = doc.get('date_str')
            time_str = doc.get('time_str')
            if not date_str or not time_str:
                continue

            price = doc.get('avg_clearing_price')
            if price is not None:
                timeslot, _ = get_timeslot_from_time_str(time_str)
                key = (date_str, timeslot)
                rt_map[key] = price
                timeslot_data[timeslot]["rt_prices"].append(price)
        
        # 5. 计算价差
        all_keys = set(da_map.keys()) | set(rt_map.keys())
        for key in all_keys:
            da_price = da_map.get(key)
            rt_price = rt_map.get(key)
            if da_price is not None and rt_price is not None:
                spread = rt_price - da_price
                timeslot = key[1]
                timeslot_data[timeslot]["spreads"].append(spread)
        
        # 6. 计算每个时段的统计指标
        timeslot_stats_list = []
        box_plot_data_list = []
        
        # 预计算全局最大值用于归一化
        all_spreads_abs = []
        all_stds = []
        temp_stats = {} 
        
        for timeslot in range(1, 49):
            data = timeslot_data[timeslot]
            spreads = data["spreads"]
            rt_prices = data["rt_prices"]
            
            if not spreads: continue
                
            avg_spread = statistics.mean(spreads)
            std_spread = statistics.stdev(spreads) if len(spreads) > 1 else 0
            
            all_spreads_abs.append(abs(avg_spread))
            all_stds.append(std_spread)
            
            temp_stats[timeslot] = {
                "avg_spread": avg_spread,
                "std_spread": std_spread,
                "data": data,
                "rt_prices": rt_prices,
                "spreads": spreads
            }
            
        max_abs_spread_global = max(all_spreads_abs) if all_spreads_abs else 1.0
        max_std_global = max(all_stds) if all_stds else 1.0
        
        # 计算风险阈值 (Top 20% 的波动性视为高风险)
        risk_threshold = 40 
        if all_stds:
            sorted_stds = sorted(all_stds)
            risk_threshold_index = int(len(sorted_stds) * 0.8)
            risk_threshold = sorted_stds[risk_threshold_index]
            risk_threshold = max(risk_threshold, 20)
            
        for timeslot in range(1, 49):
            if timeslot not in temp_stats: continue
                
            t_stat = temp_stats[timeslot]
            data = t_stat["data"]
            rt_prices = t_stat["rt_prices"]
            spreads = t_stat["spreads"]
            avg_spread = t_stat["avg_spread"]
            std_spread = t_stat["std_spread"]
            
            # 直接计算时间标签
            start_minutes = (timeslot - 1) * 30
            start_h = start_minutes // 60
            start_m = start_minutes % 60
            end_minutes = start_minutes + 30
            end_h = end_minutes // 60
            end_m = end_minutes % 60
            
            if end_h == 24:
                time_label = f"{start_h:02d}:{start_m:02d}-24:00"
            else:
                time_label = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
            
            # 基础统计
            da_prices = data["da_prices"]
            avg_price_rt = statistics.mean(rt_prices)
            avg_price_da = statistics.mean(da_prices) if da_prices else 0
            std_price_rt = statistics.stdev(rt_prices) if len(rt_prices) > 1 else 0
            max_price_rt = max(rt_prices)
            min_price_rt = min(rt_prices)
            
            positive_spreads = [s for s in spreads if s > 0]
            negative_spreads = [s for s in spreads if s < 0]
            positive_spread_ratio = len(positive_spreads) / len(spreads)
            negative_spread_ratio = len(negative_spreads) / len(spreads)
            max_spread = max(spreads)
            min_spread = min(spreads)
            sample_size = len(spreads)
            
            # 一致性评分
            consistency_score = max(positive_spread_ratio, negative_spread_ratio)
            
            # 推荐指数计算
            consistency_norm = max(0, (consistency_score - 0.5) * 2)
            spread_norm = abs(avg_spread) / max_abs_spread_global
            volatility_norm = std_price_rt / max_std_global
            
            rec_score = (0.4 * consistency_norm) + (0.4 * spread_norm) - (0.2 * volatility_norm)
            rec_score = max(0, min(1, rec_score)) * 100
            
            # 信号强度 (1-5)
            if rec_score >= 80: signal_strength = 5
            elif rec_score >= 60: signal_strength = 4
            elif rec_score >= 40: signal_strength = 3
            elif rec_score >= 20: signal_strength = 2
            else: signal_strength = 1
            
            # 策略判定
            if consistency_score >= 0.7 and abs(avg_spread) > 10:
                recommended_strategy = "做多日前" if avg_spread > 0 else "做空日前"
                confidence = "高"
            elif abs(avg_spread) > 5 and consistency_score >= 0.6:
                recommended_strategy = "做多日前" if avg_spread > 0 else "做空日前"
                confidence = "中"
            else:
                recommended_strategy = "观望"
                confidence = "低" if consistency_score < 0.5 else "中"
            
            # 风险等级
            if std_spread >= risk_threshold:
                risk_level = "高风险"
            elif std_spread >= risk_threshold * 0.6:
                risk_level = "中风险"
            else:
                risk_level = "低风险"
            
            timeslot_stats_list.append({
                "timeslot": timeslot,
                "time_label": time_label,
                "avg_price_rt": round(avg_price_rt, 2),
                "avg_price_da": round(avg_price_da, 2),
                "std_price_rt": round(std_price_rt, 2),
                "max_price_rt": round(max_price_rt, 2),
                "min_price_rt": round(min_price_rt, 2),
                "avg_spread": round(avg_spread, 2),
                "std_spread": round(std_spread, 2),
                "positive_spread_ratio": round(positive_spread_ratio, 3),
                "negative_spread_ratio": round(negative_spread_ratio, 3),
                "max_spread": round(max_spread, 2),
                "min_spread": round(min_spread, 2),
                "consistency_score": round(consistency_score, 3),
                "recommended_strategy": recommended_strategy,
                "confidence": confidence,
                "risk_level": risk_level,
                "sample_size": sample_size,
                "recommendation_index": round(rec_score, 1),
                "signal_strength": signal_strength
            })
            
            # 箱线图数据
            if spreads and len(spreads) >= 2:
                sorted_spreads = sorted(spreads)
                q1 = statistics.quantiles(sorted_spreads, n=4)[0]
                median = statistics.median(sorted_spreads)
                q3 = statistics.quantiles(sorted_spreads, n=4)[2]
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                valid_values = [v for v in sorted_spreads if lower_bound <= v <= upper_bound]
                outliers = [v for v in sorted_spreads if v < lower_bound or v > upper_bound]
                
                box_plot_data_list.append({
                    "timeslot": timeslot,
                    "time_label": time_label,
                    "min": round(min(valid_values) if valid_values else min(spreads), 2),
                    "q1": round(q1, 2),
                    "median": round(median, 2),
                    "q3": round(q3, 2),
                    "max": round(max(valid_values) if valid_values else max(spreads), 2),
                    "outliers": [round(o, 2) for o in outliers]
                })
        
        # 7. 计算 KPIs
        high_consistency_list = [t for t in timeslot_stats_list if t["consistency_score"] >= 0.7]
        high_risk_list = [t for t in timeslot_stats_list if t["risk_level"] == "高风险"]
        
        top_consistency = sorted(high_consistency_list, key=lambda x: x["consistency_score"], reverse=True)[:3]
        top_risk = sorted(high_risk_list, key=lambda x: x["std_spread"], reverse=True)[:3]
        
        kpis = {
            "high_consistency_count": len(high_consistency_list),
            "avg_consistency": round(statistics.mean([t["consistency_score"] for t in timeslot_stats_list]) if timeslot_stats_list else 0, 3),
            "recommended_count": len([t for t in timeslot_stats_list if t["recommended_strategy"] != "观望"]),
            "high_risk_count": len(high_risk_list),
            "top_consistency_timeslots": [t["time_label"].split("-")[0] for t in top_consistency],
            "top_risk_timeslots": [t["time_label"].split("-")[0] for t in top_risk]
        }
        
        return {
            "kpis": kpis,
            "timeslot_stats": timeslot_stats_list,
            "box_plot_data": box_plot_data_list
        }

    # ========== 私有辅助方法 ==========

    def _get_tou_rules(self, query_date_str: str) -> Dict[str, str]:
        """获取分时电价规则 (Base + Patch 模式) - 代理至公共服务"""
        # 将日期字符串转换为 datetime 对象传递给 get_tou_rule_by_date
        query_date = datetime.strptime(query_date_str, "%Y-%m-%d")
        return get_tou_rule_by_date(query_date, collection=self.tou_collection)

    def _format_time_point(self, point: Dict[str, Any], query_date: datetime) -> Dict[str, Any]:
        """
        格式化时间点 (处理 24:00)
        """
        ts = point.get("datetime")
        if not isinstance(ts, datetime):
            return point
            
        next_day = query_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_label = "24:00" if (ts.hour == 0 and ts.minute == 0 and ts.date() == next_day.date()) else ts.strftime("%H:%M")
        
        return {
            "time": time_label,
            "value": point.get("value"),
            "timestamp": ts.isoformat()
        }
        
