import os
import tempfile
import shutil
import logging
from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Response, Body
from webapp.tools.mongo import DATABASE
from typing import List, Dict
from datetime import datetime, timedelta
import calendar
import statistics
from bson import json_util
import json

from webapp.api import v1_retail_packages, v1_customers, v1_retail_contracts
from webapp.api import v1_forecast_base_data
from webapp.api import v1_trend_analysis
from webapp.api import v1_contract_price
from webapp.api import v1_contract_price_trend
from webapp.api import v1_short_term_load_forecast
from webapp.api import v1_medium_long_term_load_forecast
from webapp.services.package_service import PackageService
from webapp.services.pricing_engine import PricingEngine
from webapp.services.pricing_model_service import pricing_model_service
from webapp.services.tou_service import get_tou_rule_by_date, get_tou_versions, get_tou_summary

# 创建一个API路由器
router = APIRouter(prefix="/api/v1", tags=["v1"])
router.include_router(v1_retail_packages.router)
router.include_router(v1_customers.router)  # 客户管理路由
router.include_router(v1_retail_contracts.router)  # 零售合同管理路由
router.include_router(v1_forecast_base_data.router)  # 预测基础数据路由
router.include_router(v1_short_term_load_forecast.router, prefix="/short-term-load-forecast")  # 短期负荷预测路由（已在main.py中直接注册）
router.include_router(v1_medium_long_term_load_forecast.router)  # 中长期负荷预测路由
router.include_router(v1_trend_analysis.router)  # 现货趋势分析路由
router.include_router(v1_contract_price.router)  # 中长期合同价格分析路由
router.include_router(v1_contract_price_trend.router)  # 中长期趋势分析路由



logger = logging.getLogger(__name__)

# --- 集合定义 ---
USER_COLLECTION = DATABASE['user_load_data']
DA_PRICE_COLLECTION = DATABASE['day_ahead_spot_price']
RT_PRICE_COLLECTION = DATABASE['real_time_spot_price']
# TOU_RULES_COLLECTION = DATABASE['tou_rules'] # 已移至 tou_service
PRICE_SGCC_COLLECTION = DATABASE['price_sgcc']


# ##############################################################################
# 现有分析API (Existing Analysis APIs)
# ##############################################################################

@router.get("/users", summary="获取所有唯一的企业简称列表")
def get_users():
    pipeline = [
        {'$group': {'_id': "$user_name"}},
        {'$sort': {'_id': 1}}
    ]
    results = list(USER_COLLECTION.aggregate(pipeline))
    return [{"user_name": r["_id"]} for r in results if r["_id"]]

@router.get("/meters", summary="获取指定企业的户号列表")
def get_meters(user_name: str = Query(..., description="企业简称")):
    customers_collection = DATABASE['customers']
    doc = customers_collection.find_one({"short_name": user_name}, {"utility_accounts.account_id": 1})
    load_meter_ids = sorted(USER_COLLECTION.distinct("meter_id", {"user_name": user_name}))
    if not doc:
        return [{"meter_id": mid, "account_id": mid} for mid in load_meter_ids]
    accounts = [acc["account_id"] for acc in doc.get("utility_accounts", []) if acc.get("account_id")]
    if not accounts or not load_meter_ids:
        return [{"meter_id": mid, "account_id": mid} for mid in (accounts or load_meter_ids)]
    result = []
    for i, acc_id in enumerate(accounts):
        meter_id = load_meter_ids[i] if i < len(load_meter_ids) else load_meter_ids[0]
        result.append({"meter_id": meter_id, "account_id": acc_id})
    for j in range(len(accounts), len(load_meter_ids)):
        result.append({"meter_id": load_meter_ids[j], "account_id": load_meter_ids[j]})
    return result

@router.get("/load_curve", summary="获取指定电表一个或多个日期的负荷曲线")
def get_load_curve(meter_id: str = Query(..., description="电表ID"), date: List[str] = Query(..., description="查询的日期列表, 格式 YYYY-MM-DD")):
    response_data = {}
    for date_str in date:
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            end_date = start_date + timedelta(days=1)
            query = {"meter_id": meter_id, "timestamp": {"$gte": start_date, "$lt": end_date}}
            projection = {"timestamp": 1, "load_value": 1, "_id": 0}
            cursor = USER_COLLECTION.find(query, projection).sort("timestamp", 1)
            points = [{"time": doc["timestamp"].strftime("%H:%M"), "value": doc["load_value"]} for doc in cursor]
            response_data[date_str] = points
        except ValueError:
            response_data[date_str] = {"error": "Invalid date format."}
            continue
    return response_data

@router.get("/daily_energy", summary="获取指定电表一个或多个月份的日电量数据")
def get_daily_energy(meter_id: str = Query(..., description="电表ID"), month: List[str] = Query(..., description="查询的月份列表, 格式 YYYY-MM")):
    response_data = {}
    for month_str in month:
        try:
            year, mon = map(int, month_str.split('-'))
            start_date = datetime(year, mon, 1)
            end_date = datetime(year, mon, calendar.monthrange(year, mon)[1], 23, 59, 59)
            pipeline = [
                {'$match': {'meter_id': meter_id, 'timestamp': {'$gte': start_date, '$lte': end_date}}},
                {'$group': {'_id': {'$dayOfMonth': '$timestamp'}, 'energy': {'$sum': '$load_value'}}},
                {'$sort': {'_id': 1}},
                {'$project': {'day': '$_id', 'energy': '$energy', '_id': 0}}
            ]
            response_data[month_str] = list(USER_COLLECTION.aggregate(pipeline))
        except ValueError:
            response_data[month_str] = {"error": "Invalid month format."}
            continue
    return response_data


@router.get("/total_daily_energy", summary="获取所有用户汇总的日电量趋势")
def get_total_daily_energy(month: List[str] = Query(..., description="查询的月份列表, 格式 YYYY-MM")):
    response_data = {}
    for month_str in month:
        try:
            year, mon = map(int, month_str.split('-'))
            start_date = datetime(year, mon, 1)
            end_date = datetime(year, mon, calendar.monthrange(year, mon)[1], 23, 59, 59)
            pipeline = [
                {'$match': {'timestamp': {'$gte': start_date, '$lte': end_date}}},
                {'$group': {'_id': {'$dayOfMonth': '$timestamp'}, 'energy': {'$sum': '$load_value'}}},
                {'$sort': {'_id': 1}},
                {'$project': {'day': '$_id', 'energy': '$energy', '_id': 0}}
            ]
            response_data[month_str] = list(USER_COLLECTION.aggregate(pipeline))
        except ValueError:
            response_data[month_str] = {"error": "Invalid month format."}
            continue
    return response_data


@router.get("/available-dates", summary="获取指定电表所有存在数据的日期")
def get_available_dates(meter_id: str = Query(..., description="电表ID")):
    pipeline = [
        {'$match': {'meter_id': meter_id}},
        {'$project': {'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp'}}, '_id': 0}},
        {'$group': {'_id': '$date'}},
        {'$sort': {'_id': 1}}
    ]
    return [doc['_id'] for doc in USER_COLLECTION.aggregate(pipeline)]


# ##############################################################################
# 负荷分析 API (Load Analysis APIs)
# ##############################################################################

@router.get("/load_analysis/daily_curve", summary="获取日负荷曲线数据（96点）")
def get_daily_load_curve(dates: str = Query(..., description="逗号分隔的日期列表 YYYY-MM-DD")):
    date_list = [d.strip() for d in dates.split(",")]
    result = {}
    for date_str in date_list:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            start_dt = dt
            end_dt = dt + timedelta(days=1)
            cursor = USER_COLLECTION.find(
                {"timestamp": {"$gte": start_dt, "$lt": end_dt}},
                {"timestamp": 1, "load_value": 1, "user_id": 1, "_id": 0}
            ).sort("timestamp", 1)
            points = []
            for doc in cursor:
                h = doc["timestamp"].hour
                m = doc["timestamp"].minute
                time_index = h * 4 + m // 15
                points.append({"time_index": time_index, "load": doc["load_value"]})
            if points:
                result[date_str] = points
        except ValueError:
            result[date_str] = {"error": "Invalid date format"}
    return result


@router.get("/load_analysis/monthly_curve", summary="获取月度负荷曲线分析")
def get_monthly_load_curve(month: str = Query(..., description="月份 YYYY-MM")):
    try:
        year, mon = map(int, month.split("-"))
        start_dt = datetime(year, mon, 1)
        if mon < 12:
            end_dt = datetime(year, mon + 1, 1)
        else:
            end_dt = datetime(year + 1, 1, 1)

        # 从 tou_rules 获取节假日日期
        holiday_dates: set = set()
        try:
            tou_coll = DATABASE["tou_rules"]
            for patch in tou_coll.find({"type": "patch", "dates": {"$exists": True}}, {"dates": 1, "_id": 0}):
                for d in patch.get("dates", []):
                    if isinstance(d, str) and d.startswith(month):
                        holiday_dates.add(d)
        except Exception:
            pass

        # 查询全月数据，附带日期信息
        docs = list(USER_COLLECTION.find(
            {"timestamp": {"$gte": start_dt, "$lt": end_dt}},
            {"timestamp": 1, "load_value": 1, "_id": 0}
        ))

        if not docs:
            return {"month": month, "data": []}

        # 按时间点(时+分)和日期类型分组
        # key: (hour, minute) -> {monthly: [], workday: [], weekend: [], holiday: []}
        time_buckets: dict = {}
        for doc in docs:
            ts = doc.get("timestamp")
            val = doc.get("load_value")
            if not isinstance(ts, datetime) or val is None:
                continue
            h, m = ts.hour, ts.minute
            key = (h, m)
            if key not in time_buckets:
                time_buckets[key] = {"monthly": [], "workday": [], "weekend": [], "holiday": []}
            time_buckets[key]["monthly"].append(val)
            date_str = ts.strftime("%Y-%m-%d")
            if date_str in holiday_dates:
                time_buckets[key]["holiday"].append(val)
            elif ts.weekday() >= 5:
                time_buckets[key]["weekend"].append(val)
            else:
                time_buckets[key]["workday"].append(val)

        points = []
        for (h, m), buckets in sorted(time_buckets.items()):
            time_index = h * 4 + m // 15
            monthly_avg = sum(buckets["monthly"]) / len(buckets["monthly"]) if buckets["monthly"] else None
            workday_avg = sum(buckets["workday"]) / len(buckets["workday"]) if buckets["workday"] else None
            weekend_avg = sum(buckets["weekend"]) / len(buckets["weekend"]) if buckets["weekend"] else None
            holiday_avg = sum(buckets["holiday"]) / len(buckets["holiday"]) if buckets["holiday"] else None
            points.append({
                "time_index": time_index,
                "monthly_avg": round(monthly_avg, 2) if monthly_avg is not None else None,
                "workday_avg": round(workday_avg, 2) if workday_avg is not None else None,
                "weekend_avg": round(weekend_avg, 2) if weekend_avg is not None else None,
                "holiday_avg": round(holiday_avg, 2) if holiday_avg is not None else None,
                "count": len(buckets["monthly"]),
            })
        return {"month": month, "data": points}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format")


@router.get("/load_analysis/total_load_curve", summary="获取指定时间段的总负荷曲线")
def get_total_load_curve(start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
                         end_date: str = Query(..., description="结束日期 YYYY-MM-DD")):
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_dt, "$lt": end_dt}}},
            {"$group": {
                "_id": {"h": {"$hour": "$timestamp"}, "m": {"$minute": "$timestamp"}},
                "load": {"$avg": "$load_value"}
            }},
            {"$sort": {"_id.h": 1, "_id.m": 1}}
        ]
        results = list(USER_COLLECTION.aggregate(pipeline))
        points = []
        for r in results:
            h, m = r["_id"]["h"], r["_id"]["m"]
            time_index = h * 4 + m // 15
            points.append({"time_index": time_index, "load": round(r["load"], 2)})
        return points
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

@router.get("/available_months", summary="获取所有存在价格数据的月份")
def get_available_months():
    try:
        pipeline = [
            {'$project': {'month': {'$dateToString': {'format': '%Y-%m', 'date': '$datetime'}}}},
            {'$group': {'_id': '$month'}},
            {'$sort': {'_id': -1}}
        ]
        # 这里我们假设日前和实时数据的月份范围基本一致，使用日前价格集合进行查询
        months = [doc['_id'] for doc in DA_PRICE_COLLECTION.aggregate(pipeline)]
        return months
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


def get_tou_rule_for_date(date: datetime) -> Dict[str, str]:
    """
    获取指定日期的分时电价规则 (Base + Patch 模式)
    (Delegate to tou_service)
    """
    return get_tou_rule_by_date(date)

@router.get("/tou-rules/versions", summary="获取所有可用的分时电价版本")
def get_tou_rule_versions():
    """
    获取所有可用的分时电价版本日期列表
    """
    try:
        return get_tou_versions()
    except Exception as e:
        logger.error(f"Error in get_tou_rule_versions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取分时电价版本失败: {str(e)}")

@router.get("/tou-rules/summary", summary="获取指定版本的分时电价规则摘要")
def get_tou_rule_summary(version: str = Query(..., description="版本日期, 格式 YYYY-MM-DD")):
    """
    获取指定版本的分时电价规则摘要，包含全年各月的分时定义
    """
    try:
        version_date = datetime.strptime(version, "%Y-%m-%d")
        return get_tou_summary(version_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD 格式")
    except Exception as e:
        logger.error(f"Error in get_tou_rule_summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取分时电价规则摘要失败: {str(e)}")

@router.get("/price_comparison", summary="获取指定单日的日前与实时价格对比数据")
def get_price_comparison(date: str = Query(..., description="查询日期, 格式 YYYY-MM-DD")):
    try:
        start_date = datetime.strptime(date, "%Y-%m-%d")
        tou_rules = get_tou_rule_for_date(start_date)

        # 使用 date_str 查询当天所有数据
        query = {"date_str": date}
        da_docs = list(DA_PRICE_COLLECTION.find(query).sort("time_str", 1))
        rt_docs = list(RT_PRICE_COLLECTION.find(query).sort("time_str", 1))

        # 将列表转换为字典以便快速查找（使用 time_str 作为键）
        da_price_map = {doc['time_str']: doc for doc in da_docs}
        rt_price_map = {doc['time_str']: doc for doc in rt_docs}

        chart_data, da_prices_for_stats, rt_prices_for_stats = [], [], []
        tou_stats_collector = {period: {"da": [], "rt": []} for period in set(tou_rules.values())}

        # 生成96个时间点（15分钟间隔）
        time_points = []
        for i in range(96):
            total_minutes = i * 15
            hour = total_minutes // 60
            minute = total_minutes % 60
            time_str = f"{hour:02d}:{minute:02d}"
            time_points.append(time_str)

        for time_str in time_points:
            # 从字典中直接获取数据
            da_doc = da_price_map.get(time_str)
            rt_doc = rt_price_map.get(time_str)

            da_price = da_doc.get('avg_clearing_price') if da_doc else None
            rt_price = rt_doc.get('avg_clearing_price') if rt_doc else None
            period_type = tou_rules.get(time_str, "平段")

            chart_data.append({"time": time_str, "day_ahead_price": da_price, "real_time_price": rt_price, "period_type": period_type})

            if da_price is not None:
                da_prices_for_stats.append(da_price)
                if period_type in tou_stats_collector: tou_stats_collector[period_type]["da"].append(da_price)
            if rt_price is not None:
                rt_prices_for_stats.append(rt_price)
                if period_type in tou_stats_collector: tou_stats_collector[period_type]["rt"].append(rt_price)

        # --- 统计计算部分保持不变 ---
        stats = {
            "day_ahead_avg": statistics.mean(da_prices_for_stats) if da_prices_for_stats else None,
            "day_ahead_std_dev": statistics.stdev(da_prices_for_stats) if len(da_prices_for_stats) > 1 else 0,
            "day_ahead_max": max(da_prices_for_stats) if da_prices_for_stats else None,
            "day_ahead_min": min(da_prices_for_stats) if da_prices_for_stats else None,
            "real_time_avg": statistics.mean(rt_prices_for_stats) if rt_prices_for_stats else None,
            "real_time_std_dev": statistics.stdev(rt_prices_for_stats) if len(rt_prices_for_stats) > 1 else 0,
            "real_time_max": max(rt_prices_for_stats) if rt_prices_for_stats else None,
            "real_time_min": min(rt_prices_for_stats) if rt_prices_for_stats else None,
        }
        tou_stats = {}
        for period, values in tou_stats_collector.items():
            tou_stats[period] = {
                "day_ahead_avg": statistics.mean(values["da"]) if values["da"] else None,
                "real_time_avg": statistics.mean(values["rt"]) if values["rt"] else None,
            }
        flat_da_avg = tou_stats.get("平段", {}).get("day_ahead_avg")
        flat_rt_avg = tou_stats.get("平段", {}).get("real_time_avg")
        for period, values in tou_stats.items():
            if flat_da_avg and values["day_ahead_avg"] is not None: values["day_ahead_ratio"] = round(values["day_ahead_avg"] / flat_da_avg, 2)
            else: values["day_ahead_ratio"] = None
            if flat_rt_avg and values["real_time_avg"] is not None: values["real_time_ratio"] = round(values["real_time_avg"] / flat_rt_avg, 2)
            else: values["real_time_ratio"] = None
        return {"chart_data": chart_data, "stats": stats, "tou_stats": tou_stats}
    except Exception as e:
        logger.error(f"Error in get_price_comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/timeslot_analysis", summary="获取指定月份、指定时段的每日价格数据")
def get_timeslot_analysis(month: str = Query(..., description="查询月份, 格式 YYYY-MM"), slot: str = Query(..., description="查询的单个时段, 格式 HH:MM")):
    try:
        year, mon = map(int, month.split('-'))
        num_days = calendar.monthrange(year, mon)[1]
        slot_hour, slot_minute = map(int, slot.split(':'))
        
        start_date = datetime(year, mon, 1)
        end_date = start_date + timedelta(days=num_days)

        # --- 优化：使用聚合查询一次性获取所有符合条件的数据 ---
        pipeline = [
            {
                '$match': {
                    'datetime': {'$gte': start_date, '$lt': end_date},
                    '$expr': {
                        '$and': [
                            {'$eq': [{'$hour': '$datetime'}, slot_hour]},
                            {'$eq': [{'$minute': '$datetime'}, slot_minute]}
                        ]
                    }
                }
            }
        ]
        da_docs = list(DA_PRICE_COLLECTION.aggregate(pipeline))
        rt_docs = list(RT_PRICE_COLLECTION.aggregate(pipeline))

        # --- 优化：转换为以“天”为键的字典以便快速查找 ---
        da_price_map = {doc['datetime'].day: doc for doc in da_docs}
        rt_price_map = {doc['datetime'].day: doc for doc in rt_docs}

        chart_data, da_prices_for_stats, rt_prices_for_stats = [], [], []
        for day in range(1, num_days + 1):
            # --- 优化：从字典中直接获取数据 ---
            da_doc = da_price_map.get(day)
            rt_doc = rt_price_map.get(day)

            da_price = da_doc.get('avg_clearing_price') if da_doc else None
            rt_price = rt_doc.get('avg_clearing_price') if rt_doc else None
            chart_data.append({"day": day, "day_ahead_price": da_price, "real_time_price": rt_price})
            
            if da_price is not None: da_prices_for_stats.append(da_price)
            if rt_price is not None: rt_prices_for_stats.append(rt_price)

        # --- 统计计算部分保持不变 ---
        stats = {
            "day_ahead_avg": statistics.mean(da_prices_for_stats) if da_prices_for_stats else None,
            "day_ahead_std_dev": statistics.stdev(da_prices_for_stats) if len(da_prices_for_stats) > 1 else 0,
            "day_ahead_max": max(da_prices_for_stats) if da_prices_for_stats else None,
            "day_ahead_min": min(da_prices_for_stats) if da_prices_for_stats else None,
            "real_time_avg": statistics.mean(rt_prices_for_stats) if rt_prices_for_stats else None,
            "real_time_std_dev": statistics.stdev(rt_prices_for_stats) if len(rt_prices_for_stats) > 1 else 0,
            "real_time_max": max(rt_prices_for_stats) if rt_prices_for_stats else None,
            "real_time_min": min(rt_prices_for_stats) if rt_prices_for_stats else None,
        }
        return {"chart_data": chart_data, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# ##############################################################################
# 国网代购电价API (SGCC Agency Price APIs)
# ##############################################################################

@router.get("/prices/sgcc", summary="获取国网代购电价数据(分页)")
def get_sgcc_prices(page: int = 1, pageSize: int = 10):
    """
    从 price_sgcc 集合中分页获取数据文档, 并额外提供完整的图表数据。
    - **排序**: 按月份ID（_id）降序排列.
    - **分页**: 根据 page 和 pageSize 返回部分数据.
    - **投影**: 排除 `pdf_binary_data` 字段以减少响应体积.
    """
    try:
        # 获取总数
        total = PRICE_SGCC_COLLECTION.count_documents({})

        # 获取表格用的分页数据
        page_cursor = PRICE_SGCC_COLLECTION.find({}, {'pdf_binary_data': 0})
        page_cursor = page_cursor.sort('_id', -1).skip((page - 1) * pageSize).limit(pageSize)
        page_data = list(page_cursor)

        # 获取图表用的全量轻量级数据
        chart_cursor = PRICE_SGCC_COLLECTION.find(
            {},
            {
                '_id': 1, 
                'purchase_price': 1, 
                'avg_on_grid_price': 1, 
                'purchase_scale_kwh': 1
            }
        ).sort('_id', 1) # 图表数据升序
        chart_data = list(chart_cursor)

        response = {
            "total": total,
            "pageData": page_data,
            "chartData": chart_data
        }
        
        return json.loads(json_util.dumps(response))

    except Exception as e:
        logger.error(f"Error in get_sgcc_prices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取国网代购电价数据时出错: {str(e)}")

# ##############################################################################
# 定价模型API (Pricing Model APIs)
# ##############################################################################

@router.get("/pricing-models", summary="获取定价模型列表")
def get_pricing_models(
    package_type: str = Query(None, description="套餐类型：time_based/non_time_based"),
    enabled: bool = Query(None, description="是否启用")
):
    """
    获取定价模型列表

    Args:
        package_type: 套餐类型筛选（可选）
        enabled: 是否启用（可选）

    Returns:
        定价模型列表
    """
    try:
        models = pricing_model_service.list_pricing_models(
            package_type=package_type,
            enabled=enabled
        )
        return models
    except Exception as e:
        logger.error(f"Error in get_pricing_models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取定价模型列表时出错: {str(e)}")


@router.get("/pricing-models/{model_code}", summary="获取定价模型详情")
def get_pricing_model(model_code: str):
    """
    获取单个定价模型的详细信息

    Args:
        model_code: 模型代码

    Returns:
        定价模型详情
    """
    try:
        model = pricing_model_service.get_pricing_model(model_code)

        if not model:
            raise HTTPException(status_code=404, detail=f"未找到模型: {model_code}")

        return model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_pricing_model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取定价模型详情时出错: {str(e)}")


@router.post("/pricing-models/{model_code}/validate", summary="验证定价配置")
def validate_pricing_config(model_code: str, data: dict = Body(...)):
    """
    验证定价配置是否符合规则

    Args:
        model_code: 模型代码
        data: 包含 pricing_config 的字典

    Returns:
        校验结果 {"valid": bool, "errors": [], "warnings": []}
    """
    try:
        pricing_config = data.get("pricing_config", {})

        result = pricing_model_service.validate_pricing_config(
            model_code=model_code,
            config=pricing_config
        )

        return result
    except Exception as e:
        logger.error(f"Error in validate_pricing_config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"验证定价配置时出错: {str(e)}")

# ##############################################################################
# 零售套餐价格计算API (Retail Package Price Calculation APIs)
# ##############################################################################

@router.post("/retail-packages/calculate-price", summary="计算套餐价格")
async def calculate_package_price(data: dict = Body(...)):
    package_id = data.get("package_id")
    date = data.get("date")
    time_period = data.get("time_period")
    volume_mwh = data.get("volume_mwh")

    service = PackageService(DATABASE)
    package = await service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    if package['pricing_mode'] == 'fixed_linked':
        return PricingEngine.calculate_fixed_linked_price(package, date, time_period, volume_mwh)
    elif package['pricing_mode'] == 'price_spread':
        return PricingEngine.calculate_price_spread_price(package, date, time_period, volume_mwh)
    else:
        raise HTTPException(status_code=400, detail="Invalid pricing mode")

# --- 公开路由，无需认证 ---
public_router = APIRouter(prefix="/api/v1", tags=["v1-public"])

# ##############################################################################
# 市场价格分析API (Market Price Analysis APIs)
# ##############################################################################

@router.get("/market-analysis/dashboard", summary="获取市场价格总览（Market Dashboard）")
def get_market_dashboard(date_str: str = Query(..., description="查询日期, 格式 YYYY-MM-DD")):
    """
    获取指定日期的市场价格总览数据，包括：
    - 财务KPI：VWAP、TWAP、价差
    - 风险KPI：最大/最小价差、极值价格
    - 96点时序数据：价格、市场竞价空间曲线
    - 时段汇总统计：按尖峰平谷分组
    """
    try:
        start_date = datetime.strptime(date_str, "%Y-%m-%d")

        # 获取尖峰平谷规则
        tou_rules = get_tou_rule_for_date(start_date)

        # 使用 date_str 查询，精确获取业务日的所有96个数据点（00:15 到 24:00）
        query = {"date_str": date_str}
        da_docs = list(DA_PRICE_COLLECTION.find(query).sort("datetime", 1))
        rt_docs = list(RT_PRICE_COLLECTION.find(query).sort("datetime", 1))

        # 查询 actual_operation 和 real_time_generation 数据用于计算实时市场竞价空间
        start_of_day = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        actual_operation_query = {"datetime": {"$gt": start_of_day, "$lte": end_of_day}}

        actual_operation_docs = list(DATABASE['actual_operation'].find(
            actual_operation_query,
            {'_id': 0, 'datetime': 1, 'time_str': 1, 'system_load': 1, 'tieline_flow': 1}
        ).sort("datetime", 1))

        real_time_generation_docs = list(DATABASE['real_time_generation'].find(
            actual_operation_query,
            {
                '_id': 0, 'datetime': 1, 'time_str': 1,
                'wind_generation': 1, 'solar_generation': 1, 'hydro_generation': 1,
                'pumped_storage_generation': 1, 'battery_storage_generation': 1
            }
        ).sort("datetime", 1))

        # 查询 daily_release 数据用于计算日前市场竞价空间
        daily_release_docs = list(DATABASE['daily_release'].find(
            actual_operation_query,
            {
                '_id': 0, 'datetime': 1,
                'system_load_forecast': 1, 'wind_forecast': 1, 'pv_forecast': 1,
                'nonmarket_unit_forecast': 1, 'tieline_plan': 1
            }
        ).sort("datetime", 1))

        # 为了稳健合并，使用 time_str 作为key创建查找字典
        da_map = {doc['time_str']: doc for doc in da_docs}
        rt_map = {doc['time_str']: doc for doc in rt_docs}
        actual_op_map = {doc['time_str']: doc for doc in actual_operation_docs if 'time_str' in doc}
        generation_map = {doc['time_str']: doc for doc in real_time_generation_docs if 'time_str' in doc}

        # daily_release 使用 datetime 计算 time_str 作为key
        daily_release_map = {}
        for doc in daily_release_docs:
            dt = doc.get('datetime')
            if isinstance(dt, datetime):
                # 计算 time_str（格式：HH:MM，次日00:00显示为24:00）
                next_day = start_of_day + timedelta(days=1)
                if dt.hour == 0 and dt.minute == 0 and dt.date() == next_day.date():
                    time_str = "24:00"
                else:
                    time_str = dt.strftime("%H:%M")
                daily_release_map[time_str] = doc

        logger.info(f"找到 {len(actual_operation_docs)} 条 actual_operation 数据")
        logger.info(f"找到 {len(real_time_generation_docs)} 条 real_time_generation 数据")
        logger.info(f"找到 {len(daily_release_docs)} 条 daily_release 数据")
        logger.info(f"daily_release_map 包含 {len(daily_release_map)} 个时间点")

        # 初始化数据容器和KPI计算所需的变量
        time_series = []
        da_weighted_sum, da_volume_sum, rt_weighted_sum, rt_volume_sum = 0, 0, 0, 0
        da_prices, rt_prices = [], []

        max_positive_spread = {"value": float('-inf'), "time_str": "", "period": 0}
        max_negative_spread = {"value": float('inf'), "time_str": "", "period": 0}
        max_rt_price = {"value": float('-inf'), "time_str": "", "period": 0}
        min_rt_price = {"value": float('inf'), "time_str": "", "period": 0}
        
        period_collector = {}

        # 以日前数据为基础进行遍历，保证时间的完整性
        for i, da_doc in enumerate(da_docs):
            period = i + 1
            time_str = da_doc.get("time_str")
            if not time_str:
                continue

            rt_doc = rt_map.get(time_str, {}) # 从实时数据字典中查找对应时段的数据
            actual_op_data = actual_op_map.get(time_str, {})
            generation_data = generation_map.get(time_str, {})
            daily_release_data = daily_release_map.get(time_str, {})

            # 提取价格和电量
            da_price = da_doc.get('avg_clearing_price')
            da_volume = da_doc.get('total_clearing_power', 0)
            rt_price = rt_doc.get('avg_clearing_price')
            rt_volume = rt_doc.get('total_clearing_power', 0)
            rt_wind = rt_doc.get('wind_clearing_power', 0)
            rt_solar = rt_doc.get('solar_clearing_power', 0)

            # 计算市场竞价空间（日前）
            market_bidding_space_da = 0
            if daily_release_data:
                try:
                    load_forecast = float(daily_release_data.get('system_load_forecast', 0))
                    wind = float(daily_release_data.get('wind_forecast', 0))
                    pv = float(daily_release_data.get('pv_forecast', 0))
                    nonmarket = float(daily_release_data.get('nonmarket_unit_forecast', 0))
                    tieline = float(daily_release_data.get('tieline_plan', 0))

                    # 市场竞价空间（日前） = 负荷预测 - 风电 - 光伏 - 非市场化机组 - 联络线计划
                    market_bidding_space_da = load_forecast - wind - pv - nonmarket - tieline
                except (TypeError, ValueError) as e:
                    logger.warning(f"计算日前市场竞价空间失败: {e}, time_str: {time_str}")

            # 计算市场竞价空间（实时）
            market_bidding_space_rt = 0
            if actual_op_data and generation_data:
                try:
                    system_load = float(actual_op_data.get('system_load', 0))
                    tieline_flow = float(actual_op_data.get('tieline_flow', 0))
                    wind = float(generation_data.get('wind_generation', 0))
                    solar = float(generation_data.get('solar_generation', 0))
                    hydro = float(generation_data.get('hydro_generation', 0))
                    pumped_storage = float(generation_data.get('pumped_storage_generation', 0))
                    battery_storage = float(generation_data.get('battery_storage_generation', 0))

                    # 非市场化机组 = 水电 + max(抽蓄, 0) + max(储能, 0)
                    nonmarket_unit = hydro + max(pumped_storage, 0) + max(battery_storage, 0)
                    # 市场竞价空间（实时） = 系统负荷 - 风电 - 光伏 - 非市场化机组 - 联络线潮流
                    market_bidding_space_rt = system_load - wind - solar - nonmarket_unit - tieline_flow
                except (TypeError, ValueError) as e:
                    logger.warning(f"计算实时市场竞价空间失败: {e}, time_str: {time_str}")

            spread = (rt_price - da_price) if (rt_price is not None and da_price is not None) else None
            period_type = tou_rules.get(time_str, "平段")

            # 组装时序数据，确保 time_str 字段存在
            time_series.append({
                "period": period,
                "time": time_str, # 兼容旧版，或者用于调试
                "time_str": time_str, # 前端需要此字段
                "price_rt": rt_price,
                "price_da": da_price,
                "volume_rt": market_bidding_space_rt,  # 市场竞价空间（实时）
                "volume_da": market_bidding_space_da,  # 市场竞价空间（日前）
                "spread": spread,
                "period_type": period_type
            })

            # 累加用于计算KPIs
            if da_price is not None and da_volume > 0:
                da_weighted_sum += da_price * da_volume
                da_volume_sum += da_volume
                da_prices.append(da_price)

            if rt_price is not None and rt_volume > 0:
                rt_weighted_sum += rt_price * rt_volume
                rt_volume_sum += rt_volume
                rt_prices.append(rt_price)

            # 更新风险指标
            if spread is not None:
                if spread > max_positive_spread["value"]:
                    max_positive_spread.update({"value": spread, "time_str": time_str, "period": period})
                if spread < max_negative_spread["value"]:
                    max_negative_spread.update({"value": spread, "time_str": time_str, "period": period})
            if rt_price is not None:
                if rt_price > max_rt_price["value"]:
                    max_rt_price.update({"value": rt_price, "time_str": time_str, "period": period})
                if rt_price < min_rt_price["value"]:
                    min_rt_price.update({"value": rt_price, "time_str": time_str, "period": period})
            
            # 收集分时段数据
            if period_type not in period_collector:
                period_collector[period_type] = {
                    "da_weighted_sum": 0, "da_volume_sum": 0,
                    "rt_weighted_sum": 0, "rt_volume_sum": 0,
                    "rt_wind_sum": 0, "rt_solar_sum": 0, "count": 0
                }
            
            if da_price is not None and da_volume > 0:
                period_collector[period_type]["da_weighted_sum"] += da_price * da_volume
                period_collector[period_type]["da_volume_sum"] += da_volume
            if rt_price is not None and rt_volume > 0:
                period_collector[period_type]["rt_weighted_sum"] += rt_price * rt_volume
                period_collector[period_type]["rt_volume_sum"] += rt_volume
                period_collector[period_type]["rt_wind_sum"] += rt_wind
                period_collector[period_type]["rt_solar_sum"] += rt_solar
                period_collector[period_type]["count"] += 1

        # --- 后续计算逻辑保持不变 ---
        
        # 计算财务KPI
        vwap_da = da_weighted_sum / da_volume_sum if da_volume_sum > 0 else None
        vwap_rt = rt_weighted_sum / rt_volume_sum if rt_volume_sum > 0 else None
        vwap_spread = (vwap_rt - vwap_da) if (vwap_rt is not None and vwap_da is not None) else None
        twap_da = statistics.mean(da_prices) if da_prices else None
        twap_rt = statistics.mean(rt_prices) if rt_prices else None

        financial_kpis = {"vwap_rt": vwap_rt, "vwap_da": vwap_da, "vwap_spread": vwap_spread, "twap_rt": twap_rt, "twap_da": twap_da}

        # 风险KPI
        risk_kpis = {
            "max_positive_spread": max_positive_spread if max_positive_spread["value"] != float('-inf') else None,
            "max_negative_spread": max_negative_spread if max_negative_spread["value"] != float('inf') else None,
            "max_rt_price": max_rt_price if max_rt_price["value"] != float('-inf') else None,
            "min_rt_price": min_rt_price if min_rt_price["value"] != float('inf') else None
        }

        # 计算时段汇总
        period_summary = []
        period_order = ["尖峰", "高峰", "平段", "低谷", "深谷"]
        for period_name in period_order:
            if period_name not in period_collector: continue

            data = period_collector[period_name]
            vwap_da_period = data["da_weighted_sum"] / data["da_volume_sum"] if data["da_volume_sum"] > 0 else None
            vwap_rt_period = data["rt_weighted_sum"] / data["rt_volume_sum"] if data["rt_volume_sum"] > 0 else None
            vwap_spread_period = (vwap_rt_period - vwap_da_period) if (vwap_rt_period and vwap_da_period) else None
            avg_volume_rt = data["rt_volume_sum"] / data["count"] if data["count"] > 0 else None
            
            renewable_volume = data["rt_wind_sum"] + data["rt_solar_sum"]
            renewable_ratio = renewable_volume / data["rt_volume_sum"] if data["rt_volume_sum"] > 0 else None

            period_summary.append({
                "period_name": period_name, "vwap_da": vwap_da_period, "vwap_rt": vwap_rt_period,
                "vwap_spread": vwap_spread_period, "avg_volume_rt": avg_volume_rt, "renewable_ratio": renewable_ratio
            })

        return {
            "date": date_str,
            "financial_kpis": financial_kpis,
            "risk_kpis": risk_kpis,
            "time_series": time_series,
            "period_summary": period_summary
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD 格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取市场总览数据时出错: {str(e)}")


@router.get("/market-analysis/day-ahead", summary="获取日前市场分析数据")
def get_day_ahead_analysis(date: str = Query(..., description="查询日期, 格式 YYYY-MM-DD")):
    """
    获取指定日期的日前市场分析数据，包括价格、总电量、各类电源的出力及市场竞价空间。
    - **查询**: 从 `day_ahead_spot_price` 和 `daily_release` 集合获取数据。
    - **计算**: 市场竞价空间 = 负荷预测 - 风电 - 光伏 - 非市场化机组 - 联络线计划
    - **统计**: 计算价格与市场竞价空间的相关系数
    - **排序**: 按 `time_str` 升序排列。
    - **返回**: 返回包含市场竞价空间和相关系数的96个数据点列表。
    """
    try:
        # 查询日前现货价格数据（使用 date_str）
        query = {"date_str": date}
        price_docs = list(DA_PRICE_COLLECTION.find(query, {'_id': 0}).sort("time_str", 1))

        if not price_docs:
            logger.warning(f"未找到日期 {date} 的日前现货价格数据")
            return {"data": [], "metadata": {"correlation": None}}

        # 查询 daily_release 数据用于计算市场竞价空间（使用 date_str）
        daily_release_docs = list(DATABASE['daily_release'].find(
            {"date_str": date},
            {
                '_id': 0,
                'time_str': 1,
                'system_load_forecast': 1,
                'wind_forecast': 1,
                'pv_forecast': 1,
                'nonmarket_unit_forecast': 1,
                'tieline_plan': 1
            }
        ).sort("time_str", 1))

        logger.info(f"找到 {len(daily_release_docs)} 条 daily_release 数据")

        # 创建 time_str -> daily_release 数据的映射
        daily_release_map = {doc['time_str']: doc for doc in daily_release_docs}

        # 合并数据并计算市场竞价空间
        result = []
        matched_count = 0
        # 用于计算相关系数的数据
        prices = []
        spaces = []

        for price_doc in price_docs:
            time_str = price_doc.get('time_str')

            # 获取对应的 daily_release 数据
            release_data = daily_release_map.get(time_str, {})

            if release_data:
                matched_count += 1
                # 计算市场竞价空间（单位：MW）
                # 市场竞价空间 = 负荷预测 - 风电 - 光伏 - 非市场化机组 - 联络线计划
                try:
                    load_forecast = float(release_data.get('system_load_forecast', 0))
                    wind = float(release_data.get('wind_forecast', 0))
                    pv = float(release_data.get('pv_forecast', 0))
                    nonmarket = float(release_data.get('nonmarket_unit_forecast', 0))
                    tieline = float(release_data.get('tieline_plan', 0))

                    market_bidding_space = load_forecast - wind - pv - nonmarket - tieline
                    price_doc['market_bidding_space'] = round(market_bidding_space, 2)

                    # 收集用于计算相关系数的数据
                    price_val = price_doc.get('avg_clearing_price')
                    if price_val is not None:
                        prices.append(float(price_val))
                        spaces.append(market_bidding_space)
                except (TypeError, ValueError) as e:
                    logger.warning(f"数值转换失败: {e}, 数据: {release_data}")
                    price_doc['market_bidding_space'] = 0
            else:
                # 如果没有匹配的数据，设置为0
                price_doc['market_bidding_space'] = 0

            result.append(price_doc)

        # 计算相关系数
        correlation = None
        if len(prices) >= 2 and len(spaces) >= 2:
            try:
                # 使用皮尔逊相关系数公式
                import numpy as np
                correlation = float(np.corrcoef(prices, spaces)[0, 1])
            except Exception as e:
                logger.warning(f"计算相关系数失败: {e}")

        logger.info(f"匹配到 {matched_count} 条数据，总共返回 {len(result)} 条记录，相关系数: {correlation}")

        # 返回数据和元信息
        response_data = {
            "data": result,
            "metadata": {
                "correlation": round(correlation * 100, 1) if correlation is not None else None
            }
        }

        return json.loads(json_util.dumps(response_data))

    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD 格式")
    except Exception as e:
        logger.error(f"获取日前市场分析数据时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取日前市场分析数据时出错: {str(e)}")


@router.get("/market-analysis/real-time", summary="获取现货市场复盘数据")
def get_real_time_analysis(date: str = Query(..., description="查询日期, 格式 YYYY-MM-DD")):
    """
    获取指定日期的现货市场复盘数据，包括价格、电量、电源出力、价格波动以及市场竞价空间。
    - **查询**: 从 `real_time_spot_price`、`actual_operation` 和 `real_time_generation` 集合获取数据。
    - **计算**:
      1. 价格爬坡（price_ramp）
      2. 市场竞价空间 = 系统负荷 - 风电 - 光伏 - 非市场化机组 - 联络线潮流
      3. 非市场化机组 = 水电 + max(抽蓄, 0) + max(储能, 0)
      4. 价格与市场竞价空间的相关系数
    - **返回**: 返回包含计算字段和相关系数的96个数据点列表。
    """
    try:
        # 查询实时现货价格数据（使用 date_str）
        query = {"date_str": date}
        price_docs = list(RT_PRICE_COLLECTION.find(query, {'_id': 0}).sort("time_str", 1))

        if not price_docs:
            logger.warning(f"未找到日期 {date} 的实时现货价格数据")
            return {"data": [], "metadata": {"correlation": None}}

        # 查询 actual_operation 数据（系统负荷和联络线潮流，使用 date_str）
        actual_operation_docs = list(DATABASE['actual_operation'].find(
            {"date_str": date},
            {'_id': 0, 'time_str': 1, 'system_load': 1, 'tieline_flow': 1}
        ).sort("time_str", 1))

        # 查询 real_time_generation 数据（风电、光伏、水电、抽蓄、储能，使用 date_str）
        real_time_generation_docs = list(DATABASE['real_time_generation'].find(
            {"date_str": date},
            {
                '_id': 0,
                'time_str': 1,
                'wind_generation': 1,
                'solar_generation': 1,
                'hydro_generation': 1,
                'pumped_storage_generation': 1,
                'battery_storage_generation': 1
            }
        ).sort("time_str", 1))

        logger.info(f"找到 {len(actual_operation_docs)} 条 actual_operation 数据")
        logger.info(f"找到 {len(real_time_generation_docs)} 条 real_time_generation 数据")

        # 创建 time_str -> 数据的映射
        actual_operation_map = {doc['time_str']: doc for doc in actual_operation_docs}
        real_time_generation_map = {doc['time_str']: doc for doc in real_time_generation_docs}

        # 合并数据并计算市场竞价空间和价格波动
        result = []
        matched_count = 0
        # 用于计算相关系数的数据
        prices = []
        spaces = []

        for i, price_doc in enumerate(price_docs):
            time_str = price_doc.get('time_str')

            # 计算价格爬坡
            if i > 0 and price_doc.get('avg_clearing_price') is not None and price_docs[i-1].get('avg_clearing_price') is not None:
                price_ramp = price_doc['avg_clearing_price'] - price_docs[i-1]['avg_clearing_price']
                price_doc['price_ramp'] = round(price_ramp, 2)
            else:
                price_doc['price_ramp'] = 0

            # 获取对应的数据
            actual_op_data = actual_operation_map.get(time_str, {})
            generation_data = real_time_generation_map.get(time_str, {})

            if actual_op_data and generation_data:
                matched_count += 1
                try:
                    # 获取系统负荷和联络线潮流
                    system_load = float(actual_op_data.get('system_load', 0))
                    tieline_flow = float(actual_op_data.get('tieline_flow', 0))

                    # 获取发电出力
                    wind = float(generation_data.get('wind_generation', 0))
                    solar = float(generation_data.get('solar_generation', 0))
                    hydro = float(generation_data.get('hydro_generation', 0))
                    pumped_storage = float(generation_data.get('pumped_storage_generation', 0))
                    battery_storage = float(generation_data.get('battery_storage_generation', 0))

                    # 计算非市场化机组出力 = 水电 + max(抽蓄, 0) + max(储能, 0)
                    nonmarket_unit = hydro + max(pumped_storage, 0) + max(battery_storage, 0)

                    # 计算市场竞价空间（单位：MW）
                    # 市场竞价空间 = 系统负荷 - 风电 - 光伏 - 非市场化机组 - 联络线潮流
                    market_bidding_space = system_load - wind - solar - nonmarket_unit - tieline_flow
                    price_doc['market_bidding_space'] = round(market_bidding_space, 2)

                    # 收集用于计算相关系数的数据
                    price_val = price_doc.get('avg_clearing_price')
                    if price_val is not None:
                        prices.append(float(price_val))
                        spaces.append(market_bidding_space)
                except (TypeError, ValueError) as e:
                    logger.warning(f"数值转换失败: {e}")
                    price_doc['market_bidding_space'] = 0
            else:
                # 如果没有匹配的数据，设置为0
                price_doc['market_bidding_space'] = 0

            result.append(price_doc)

        # 计算相关系数
        correlation = None
        if len(prices) >= 2 and len(spaces) >= 2:
            try:
                # 使用皮尔逊相关系数公式
                import numpy as np
                # 价格与市场竞价空间的相关系数
                correlation = float(np.corrcoef(prices, spaces)[0, 1])
            except Exception as e:
                logger.warning(f"计算价格与市场竞价空间相关系数失败: {e}")

        logger.info(f"匹配到 {matched_count} 条数据，总共返回 {len(result)} 条记录")
        logger.info(f"价格与市场竞价空间相关系数: {correlation}")

        # 返回数据和元信息
        response_data = {
            "data": result,
            "metadata": {
                "correlation": round(correlation * 100, 1) if correlation is not None else None
            }
        }

        return json.loads(json_util.dumps(response_data))

    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD 格式")
    except Exception as e:
        logger.error(f"获取实时市场分析数据时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取实时市场分析数据时出错: {str(e)}")


@router.get("/market-analysis/spread-attribution", summary="获取价差归因分析数据")
def get_spread_attribution_analysis(date: str = Query(..., description="查询日期, 格式 YYYY-MM-DD")):
    try:
        logger.info(f"开始处理价差归因分析请求，日期: {date}")

        # 步骤1: 获取价格数据
        try:
            logger.info("步骤1: 获取价格数据")
            query = {"date_str": date}
            da_docs = list(DA_PRICE_COLLECTION.find(query, {'_id': 0}).sort("time_str", 1))
            rt_docs = list(RT_PRICE_COLLECTION.find(query, {'_id': 0}).sort("time_str", 1))
            logger.info(f"获取到 {len(da_docs)} 条日前数据，{len(rt_docs)} 条实时数据")
        except Exception as e:
            logger.error(f"步骤1失败: {e}")
            raise

        if not da_docs or not rt_docs:
            return {"time_series": [], "systematic_bias": []}

        # 转换为字典以便快速查找
        rt_map = {doc['time_str']: doc for doc in rt_docs}
        da_map = {doc['time_str']: doc for doc in da_docs}

        # 步骤2: 查询市场竞价空间相关数据
        try:
            logger.info("步骤2: 查询市场竞价空间相关数据")
            # 查询日前市场竞价空间数据（daily_release）
            daily_release_docs = list(DATABASE['daily_release'].find(
                {"date_str": date},
                {
                    '_id': 0, 'time_str': 1,
                    'system_load_forecast': 1, 'wind_forecast': 1, 'pv_forecast': 1,
                    'nonmarket_unit_forecast': 1, 'tieline_plan': 1
                }
            ).sort("time_str", 1))

            # 查询实时市场竞价空间数据（actual_operation + real_time_generation）
            actual_operation_docs = list(DATABASE['actual_operation'].find(
                {"date_str": date},
                {'_id': 0, 'time_str': 1, 'system_load': 1, 'tieline_flow': 1}
            ).sort("time_str", 1))

            real_time_generation_docs = list(DATABASE['real_time_generation'].find(
                {"date_str": date},
                {
                    '_id': 0, 'time_str': 1,
                    'wind_generation': 1, 'solar_generation': 1, 'hydro_generation': 1,
                    'pumped_storage_generation': 1, 'battery_storage_generation': 1
                }
            ).sort("time_str", 1))
            logger.info("步骤2完成")
        except Exception as e:
            logger.error(f"步骤2失败: {e}")
            raise

        # 创建映射字典
        logger.info("步骤3: 创建映射字典")
        daily_release_map = {doc['time_str']: doc for doc in daily_release_docs}
        actual_op_map = {doc['time_str']: doc for doc in actual_operation_docs}
        generation_map = {doc['time_str']: doc for doc in real_time_generation_docs}
        logger.info(f"映射字典创建完成: daily_release={len(daily_release_map)}, actual_op={len(actual_op_map)}, generation={len(generation_map)}")

        # 步骤4: 获取分时电价规则
        try:
            logger.info("步骤4: 获取分时电价规则")
            from datetime import datetime
            tou_rules = get_tou_rule_by_date(datetime.strptime(date, "%Y-%m-%d"), collection=DATABASE['tou_rules'])
            logger.info(f"分时电价规则获取完成，包含 {len(tou_rules)} 个时间点")
        except Exception as e:
            logger.error(f"步骤4失败: {e}")
            raise

        time_series = []
        period_collector = {}

        # 4. 以日前数据为基准，计算96点偏差
        for da_point in da_docs:
            time_str = da_point.get("time_str")
            if not time_str:
                continue

            rt_point = rt_map.get(time_str, {})
            daily_release_data = daily_release_map.get(time_str, {})
            actual_op_data = actual_op_map.get(time_str, {})
            generation_data = generation_map.get(time_str, {})

            # 计算价格偏差
            price_spread = (rt_point.get('avg_clearing_price') - da_point.get('avg_clearing_price')) \
                if rt_point.get('avg_clearing_price') is not None and da_point.get('avg_clearing_price') is not None else None

            # 计算日前市场竞价空间
            market_bidding_space_da = 0
            if daily_release_data:
                try:
                    load_forecast = float(daily_release_data.get('system_load_forecast', 0))
                    wind = float(daily_release_data.get('wind_forecast', 0))
                    pv = float(daily_release_data.get('pv_forecast', 0))
                    nonmarket = float(daily_release_data.get('nonmarket_unit_forecast', 0))
                    tieline = float(daily_release_data.get('tieline_plan', 0))
                    market_bidding_space_da = load_forecast - wind - pv - nonmarket - tieline
                except (TypeError, ValueError):
                    pass

            # 计算实时市场竞价空间
            market_bidding_space_rt = 0
            if actual_op_data and generation_data:
                try:
                    system_load = float(actual_op_data.get('system_load', 0))
                    tieline_flow = float(actual_op_data.get('tieline_flow', 0))
                    wind = float(generation_data.get('wind_generation', 0))
                    solar = float(generation_data.get('solar_generation', 0))
                    hydro = float(generation_data.get('hydro_generation', 0))
                    pumped_storage = float(generation_data.get('pumped_storage_generation', 0))
                    battery_storage = float(generation_data.get('battery_storage_generation', 0))
                    nonmarket_unit = hydro + max(pumped_storage, 0) + max(battery_storage, 0)
                    market_bidding_space_rt = system_load - wind - solar - nonmarket_unit - tieline_flow
                except (TypeError, ValueError):
                    pass

            # 计算竞价空间偏差(实时 - 日前)
            bidding_space_deviation = market_bidding_space_rt - market_bidding_space_da

            # 计算各维度偏差(实时 - 日前)
            system_load_deviation = 0
            renewable_deviation = 0
            nonmarket_unit_deviation = 0
            tieline_deviation = 0

            # 初始化原始数据变量（默认为0，避免未定义错误）
            load_forecast = 0
            wind_forecast = 0
            pv_forecast = 0
            nonmarket_forecast = 0
            tieline_plan = 0
            system_load = 0
            tieline_flow = 0
            wind_rt = 0
            solar_rt = 0
            nonmarket_unit_rt = 0

            if daily_release_data and actual_op_data and generation_data:
                try:
                    # 提取日前预测数据
                    load_forecast = float(daily_release_data.get('system_load_forecast', 0))
                    wind_forecast = float(daily_release_data.get('wind_forecast', 0))
                    pv_forecast = float(daily_release_data.get('pv_forecast', 0))
                    nonmarket_forecast = float(daily_release_data.get('nonmarket_unit_forecast', 0))
                    tieline_plan = float(daily_release_data.get('tieline_plan', 0))

                    # 提取实时数据
                    system_load = float(actual_op_data.get('system_load', 0))
                    tieline_flow = float(actual_op_data.get('tieline_flow', 0))
                    wind_rt = float(generation_data.get('wind_generation', 0))
                    solar_rt = float(generation_data.get('solar_generation', 0))
                    hydro_rt = float(generation_data.get('hydro_generation', 0))
                    pumped_storage_rt = float(generation_data.get('pumped_storage_generation', 0))
                    battery_storage_rt = float(generation_data.get('battery_storage_generation', 0))

                    # 计算实时非市场化机组 = 水电 + max(抽蓄, 0) + max(储能, 0)
                    nonmarket_unit_rt = hydro_rt + max(pumped_storage_rt, 0) + max(battery_storage_rt, 0)

                    # 计算各维度偏差
                    system_load_deviation = system_load - load_forecast
                    renewable_deviation = (wind_rt + solar_rt) - (wind_forecast + pv_forecast)
                    nonmarket_unit_deviation = nonmarket_unit_rt - nonmarket_forecast
                    tieline_deviation = tieline_flow - tieline_plan
                except (TypeError, ValueError) as e:
                    logger.warning(f"计算偏差失败: {e}, time_str: {time_str}")

            point_data = {
                "time_str": time_str,
                "price_spread": price_spread,
                "total_volume_deviation": bidding_space_deviation,  # 竞价空间偏差
                "system_load_deviation": system_load_deviation,
                "renewable_deviation": renewable_deviation,
                "nonmarket_unit_deviation": nonmarket_unit_deviation,
                "tieline_deviation": tieline_deviation,
                # 添加日前和实时的原始数据用于前端曲线对比
                "system_load_da": load_forecast,
                "system_load_rt": system_load,
                "renewable_da": wind_forecast + pv_forecast,
                "renewable_rt": wind_rt + solar_rt,
                "nonmarket_unit_da": nonmarket_forecast,
                "nonmarket_unit_rt": nonmarket_unit_rt,
                "tieline_da": tieline_plan,
                "tieline_rt": tieline_flow
            }
            time_series.append(point_data)

            # 4. 聚合数据到分时段
            period_type = tou_rules.get(time_str, "平段")
            if period_type not in period_collector:
                period_collector[period_type] = {key: [] for key in point_data if key != 'time_str'}
            
            for key, value in point_data.items():
                if key != 'time_str' and value is not None:
                    period_collector[period_type][key].append(value)

        # 5. 计算系统性偏差
        systematic_bias = []
        period_order = ["尖峰", "高峰", "平段", "低谷", "深谷"]
        for period_name in period_order:
            if period_name in period_collector:
                agg_data = {"period_name": period_name}
                for key, values in period_collector[period_name].items():
                    if values:
                        agg_data[f"avg_{key}"] = statistics.mean(values)
                    else:
                        agg_data[f"avg_{key}"] = None
                systematic_bias.append(agg_data)

        # 6. 计算价差分布直方图
        price_spreads = [point['price_spread'] for point in time_series if point['price_spread'] is not None]

        price_distribution = []
        if price_spreads:
            # 找出最小值和最大值
            min_spread = min(price_spreads)
            max_spread = max(price_spreads)

            # 动态计算区间宽度（目标：10-15个区间）
            spread_range = max_spread - min_spread
            if spread_range > 0:
                # 选择合适的区间宽度（5, 10, 20, 50等）
                bin_width_candidates = [5, 10, 20, 50, 100]
                bin_width = 10  # 默认10
                for width in bin_width_candidates:
                    num_bins = spread_range / width
                    if 10 <= num_bins <= 20:
                        bin_width = width
                        break

                # 计算区间起点和终点
                bin_start = (min_spread // bin_width) * bin_width
                bin_end = ((max_spread // bin_width) + 1) * bin_width

                # 创建区间并统计
                current = bin_start
                while current < bin_end:
                    bin_min = current
                    bin_max = current + bin_width
                    # 统计落在此区间的价差数量
                    count = sum(1 for spread in price_spreads if bin_min <= spread < bin_max)

                    if count > 0:  # 只添加有数据的区间
                        price_distribution.append({
                            "range_min": bin_min,
                            "range_max": bin_max,
                            "range_label": f"{bin_min:.0f}~{bin_max:.0f}",
                            "count": count
                        })

                    current += bin_width

        return {
            "time_series": time_series,
            "systematic_bias": systematic_bias,
            "price_distribution": price_distribution
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD 格式")
    except Exception as e:
        import traceback
        error_details = f"获取价差归因分析数据时出错: {str(e)}\n\n调用栈:\n{traceback.format_exc()}"
        logger.error(error_details)
        raise HTTPException(status_code=500, detail=error_details)


@public_router.get("/prices/sgcc/{month}/pdf", summary="获取指定月份的国网代购电价PDF公告")
def get_sgcc_price_pdf(month: str):
    """
    根据月份ID（例如, '2024-01'）获取对应的PDF文件.
    - **查询**: 根据 `_id` 查找单个文档.
    - **返回**: 如果找到PDF，则以流式响应返回；否则返回404错误.
    """
    try:
        document = PRICE_SGCC_COLLECTION.find_one({'_id': month}, {'pdf_binary_data': 1, 'attachment_name': 1})
        if document and 'pdf_binary_data' in document and document['pdf_binary_data']:
            pdf_bytes = document['pdf_binary_data']
            logger.debug(f"Found PDF for month {month}. Size: {len(pdf_bytes)} bytes.")
            attachment_name = document.get('attachment_name', f"sgcc_price_{month}.pdf")

            headers = {
                'Content-Disposition': f'inline; filename="{attachment_name}"'
            }
            return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
        else:
            logger.warning(f"PDF not found or empty for month {month}.")
            raise HTTPException(status_code=404, detail=f"未找到月份 {month} 的PDF文件或文件为空.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_sgcc_price_pdf: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取PDF文件时出错: {str(e)}")
