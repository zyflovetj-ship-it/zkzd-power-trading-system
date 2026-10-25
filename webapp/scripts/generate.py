#!/usr/bin/env python3
"""全业务数据初始化脚本 - 2026年7月江苏省电力交易数据"""
import logging, math, random, sys, os
from datetime import datetime, timedelta, date
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from webapp.tools.mongo import DATABASE
from bson import ObjectId

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
db = DATABASE
random.seed(42)

JULY_DATES = [date(2026, 7, d) for d in range(1, 32)]

def gen_price(h, m, base=350, vol=80):
    hf = h + m / 60.0
    mr = max(0, min(1, (hf - 5) / 4)) * 120
    mp = max(0, math.sin((hf - 9) * math.pi / 6)) * 150 if 9 <= hf <= 15 else 0
    ep = max(0, math.sin((hf - 17) * math.pi / 8)) * 180 if 17 <= hf <= 25 else 0
    nv = -80 if hf >= 23 or hf < 6 else 0
    return max(100, min(800, base + mr + mp + ep + nv + random.uniform(-vol, vol)))

def gen_load(h, m, base=35000, is_weekend=False):
    hf = h + m / 60.0
    w = 0.75 if is_weekend else 1.0
    nb = base * 0.6
    mr = max(0, (hf - 6) / 4) * base * 0.3 if hf >= 6 else 0
    nd = max(0, -abs(hf - 13) / 2 + 2) * base * 0.05 if 12 <= hf <= 15 else 0
    er = max(0, (hf - 17) / 3) * base * 0.2 if 17 <= hf <= 21 else 0
    return max(15000, min(60000, (nb + mr - nd + er) * w + random.uniform(-2000, 2000)))

def gen_wind(h, m):
    hf = h + m / 60.0
    return max(500, random.uniform(3000, 5000) + 2000 * math.sin((hf - 2) * math.pi / 12) + random.uniform(-1000, 1000))

def gen_solar(h, m):
    hf = h + m / 60.0
    return random.uniform(0, 100) if hf < 5 or hf > 19 else max(0, 8000 * math.sin((hf - 6) * math.pi / 13) + random.uniform(-500, 500))

def gen_ts(i, d):
    if i == 95:
        from datetime import timedelta
        return datetime(2026, 7, d.day) + timedelta(days=1), '24:00'
    h, m = i // 4, (i % 4) * 15
    dt = datetime(2026, 7, d.day, h, m)
    return dt, dt.strftime('%H:%M')

def gen_vol(h, m):
    hf = h + m / 60.0
    bv = random.uniform(30000, 50000)
    pf = 1.3 if 9 <= hf <= 12 else (1.4 if 17 <= hf <= 21 else (0.6 if hf >= 23 or hf < 6 else 1.0))
    return max(5000, bv * pf + random.uniform(-3000, 3000))

print('=== 1. 清空现有数据 ===')
for c in ['customers', 'retail_packages', 'retail_contracts', 'pricing_models',
          'day_ahead_spot_price', 'real_time_spot_price', 'actual_operation',
          'real_time_generation', 'daily_release', 'user_load_data',
          'short_term_load_forecast', 'forecast_accuracy_daily', 'weekly_forecast',
          'price_forecast_results', 'medium_long_term_reviews',
          'monthly_trading_strategies', 'd2_trading_strategies', 'contract_curves',
          'medium_long_term_load_forecast', 'task_configs', 'task_execution_logs',
          'task_retry_requests', 'daily_reports', 'monthly_price_trends',
          'tou_rules', 'price_sgcc']:
    db[c].delete_many({})
    print(f'  Cleared {c}')

print('=== 2. 客户数据 (15个) ===')
CUSTOMERS = [
    ('苏州工业园区华兴科技有限公司','华兴科技','工商业','制造业','10kV','苏州市','工业园区','苏州工业园区星海街200号','李明','13912345678','active'),
    ('南京钢铁集团股份有限公司','南钢集团','大工业','钢铁','110kV','南京市','六合区','南京市六合区卸甲甸','王强','13912345679','active'),
    ('无锡威孚高科技集团','威孚高科','工商业','制造业','35kV','无锡市','新吴区','无锡市新吴区华山路5号','张伟','13912345680','active'),
    ('常州天合光能有限公司','天合光能','大工业','新能源','110kV','常州市','新北区','常州市新北区天合路2号','刘芳','13912345681','active'),
    ('徐工集团工程机械有限公司','徐工集团','大工业','机械制造','35kV','徐州市','鼓楼区','徐州市经济开发区','陈刚','13912345682','active'),
    ('南通醋酸纤维有限公司','南通醋纤','工商业','化工','35kV','南通市','崇川区','南通市崇川区钟秀路109号','赵敏','13912345683','active'),
    ('扬州亚星客车股份有限公司','亚星客车','工商业','汽车制造','10kV','扬州市','邗江区','扬州市汽车产业园','孙涛','13912345684','active'),
    ('镇江奇美化工有限公司','镇江奇美','工商业','化工','35kV','镇江市','镇江新区','镇江市大港经济开发区','周丽','13912345685','active'),
    ('泰州隆基乐叶光伏有限公司','隆基乐叶','大工业','新能源','110kV','泰州市','海陵区','泰州市海陵区九龙镇','吴昊','13912345686','active'),
    ('盐城东山精密制造有限公司','东山精密','工商业','电子制造','10kV','盐城市','盐都区','盐城市盐都区高新区','郑杰','13912345687','active'),
    ('淮安今世缘酒业股份有限公司','今世缘酒业','工商业','食品饮料','10kV','淮安市','涟水县','淮安市涟水县高沟镇','黄勇','13912345688','active'),
    ('连云港恒瑞医药股份有限公司','恒瑞医药','工商业','医药','10kV','连云港市','连云区','连云港经济技术开发区','许文','13912345689','active'),
    ('宿迁可成科技有限公司','可成科技','工商业','电子制造','35kV','宿迁市','宿城区','宿迁市苏宿工业园区','何明','13912345690','prospect'),
    ('江苏新时代造船有限公司','新时代造船','大工业','船舶制造','35kV','泰州市','靖江市','泰州市靖江市新港园区','马超','13912345691','pending'),
    ('昆山纬创资通有限公司','纬创资通','工商业','电子制造','10kV','苏州市','昆山市','昆山市综合保税区','高峰','13912345692','active'),
]
for i, (n, sn, ut, ind, v, reg, dist, addr, cp, cph, st) in enumerate(CUSTOMERS):
    db.customers.insert_one({
        '_id': ObjectId(), 'user_name': n, 'short_name': sn, 'user_type': ut,
        'industry': ind, 'voltage': v, 'region': reg, 'district': dist,
        'address': addr, 'contact_person': cp, 'contact_phone': cph,
        'status': st, 'created_at': datetime(2026, 6, 1), 'updated_at': datetime(2026, 7, 1),
        'created_by': 'admin', 'updated_by': 'admin',
        'utility_accounts': [
            {'account_id': f'UA{1000+i}_{j}', 'metering_points': [
                {'metering_point_id': f'MP{1000+i}_{j}_{k}', 'allocation_percentage': 100.0,
                 'meter': {'meter_id': f'MTR{1000+i}_{j}_{k}', 'multiplier': 1.0}}
                for k in range(2)]}
            for j in range(2)]
    })
print(f'  Created {len(CUSTOMERS)} customers')

print('=== 3. 定价模型 (14个) ===')
PM = [
    ('fixed_linked_fee_time','固定价差-费用联动-分时','time_based','fixed_linked','fee',1),
    ('fixed_linked_fee_non_time','固定价差-费用联动-不分时','non_time_based','fixed_linked','fee',2),
    ('fixed_linked_price_time','固定价差-价格联动-分时','time_based','fixed_linked','price',3),
    ('fixed_linked_price_non_time','固定价差-价格联动-不分时','non_time_based','fixed_linked','price',4),
    ('reference_linked_fee_time','参照联动-费用联动-分时','time_based','reference_linked','fee',5),
    ('reference_linked_fee_non_time','参照联动-费用联动-不分时','non_time_based','reference_linked','fee',6),
    ('reference_linked_price_time','参照联动-价格联动-分时','time_based','reference_linked','price',7),
    ('reference_linked_price_non_time','参照联动-价格联动-不分时','non_time_based','reference_linked','price',8),
    ('price_spread_simple_fee','简单价差分成-费用','non_time_based','price_spread_simple','fee',9),
    ('price_spread_simple_price','简单价差分成-价格','non_time_based','price_spread_simple','price',10),
    ('price_spread_formula_fee','公式价差分成-费用','non_time_based','price_spread_formula','fee',11),
    ('price_spread_formula_price','公式价差分成-价格','non_time_based','price_spread_formula','price',12),
    ('single_comprehensive_time','单一综合价-分时','time_based','single_comprehensive',None,13),
    ('single_comprehensive_non_time','单一综合价-不分时','non_time_based','single_comprehensive',None,14),
]
for code, name, pt, pm_m, ft, so in PM:
    db.pricing_models.insert_one({
        '_id': ObjectId(), 'model_code': code, 'display_name': name,
        'package_type': pt, 'pricing_mode': pm_m, 'floating_type': ft,
        'formula': f'<p>{name}</p>', 'description': f'<p>{name}定价模型</p>',
        'enabled': True, 'sort_order': so, 'created_at': datetime(2026, 1, 1),
        'updated_at': datetime(2026, 7, 1)
    })
print(f'  Created {len(PM)} pricing models')

print('=== 4. 零售套餐 (9个) ===')
PKGS = [
    ('江苏固定价差套餐（分时-费用联动）','time_based','fixed_linked_fee_time',False,{'peak_price':0.45,'flat_price':0.38,'valley_price':0.25,'service_fee':0.03}),
    ('江苏固定价差套餐（不分时-费用联动）','non_time_based','fixed_linked_fee_non_time',False,{'fixed_price':0.40,'service_fee':0.025}),
    ('江苏固定价差套餐（分时-价格联动）','time_based','fixed_linked_price_time',False,{'peak_ratio':1.15,'flat_ratio':1.08,'valley_ratio':0.95,'reference_price':0.38}),
    ('绿电固定价差套餐（不分时）','non_time_based','fixed_linked_fee_non_time',True,{'fixed_price':0.42,'service_fee':0.04}),
    ('单一综合价套餐（分时）','time_based','single_comprehensive_time',False,{'peak_price':0.48,'flat_price':0.40,'valley_price':0.28}),
    ('单一综合价套餐（不分时）','non_time_based','single_comprehensive_non_time',False,{'fixed_price':0.42}),
    ('参照联动套餐（分时-费用联动）','time_based','reference_linked_fee_time',False,{'peak_price':0.44,'flat_price':0.37,'valley_price':0.24,'service_fee':0.015}),
    ('简单价差分成套餐','non_time_based','price_spread_simple_fee',False,{'retail_price':0.40,'spread_ratio':0.3}),
    ('公式价差分成套餐','non_time_based','price_spread_formula_fee',False,{'retail_price':0.42,'spread_ratio':0.5}),
]
for i, (pn, pt, mc, gp, pc) in enumerate(PKGS):
    st = 'active' if i < 7 and i != 6 else ('draft' if i == 6 else 'active')
    db.retail_packages.insert_one({
        '_id': ObjectId(), 'package_name': pn, 'package_type': pt, 'model_code': mc,
        'is_green_power': gp, 'pricing_config': pc, 'status': st,
        'created_at': datetime(2026, 6, 15), 'updated_at': datetime(2026, 7, 1),
        'created_by': 'admin', 'updated_by': 'admin',
        'activated_at': datetime(2026, 7, 1) if st == 'active' else None
    })
print(f'  Created {len(PKGS)} packages')

print('=== 5. 零售合同 (13个) ===')
all_custs = list(db.customers.find())
all_pkgs = list(db.retail_packages.find({'status': 'active'}))
for i in range(min(8, len(all_custs))):
    p = all_pkgs[i % len(all_pkgs)]
    db.retail_contracts.insert_one({'_id': ObjectId(),
        'contract_name': f'{all_custs[i]["short_name"]}-{p["package_name"][:8]}-202607',
        'package_name': p['package_name'], 'package_id': str(p['_id']),
        'customer_name': all_custs[i]['user_name'], 'customer_id': str(all_custs[i]['_id']),
        'purchasing_electricity_quantity': random.uniform(500000, 3000000),
        'purchase_start_month': datetime(2026, 7, 1), 'purchase_end_month': datetime(2026, 12, 31),
        'package_snapshot': {'package_type': p['package_type'], 'model_code': p['model_code'],
            'is_green_power': p.get('is_green_power', False), 'pricing_config': p.get('pricing_config', {})},
        'created_by': 'admin', 'created_at': datetime(2026, 6, 20),
        'updated_by': 'admin', 'updated_at': datetime(2026, 7, 1)})
for i in range(min(3, len(all_custs))):
    p = all_pkgs[i % len(all_pkgs)]
    db.retail_contracts.insert_one({'_id': ObjectId(),
        'contract_name': f'{all_custs[i]["short_name"]}-{p["package_name"][:8]}-202701',
        'package_name': p['package_name'], 'package_id': str(p['_id']),
        'customer_name': all_custs[i]['user_name'], 'customer_id': str(all_custs[i]['_id']),
        'purchasing_electricity_quantity': random.uniform(500000, 2000000),
        'purchase_start_month': datetime(2027, 1, 1), 'purchase_end_month': datetime(2027, 12, 31),
        'package_snapshot': {'package_type': p['package_type'], 'model_code': p['model_code'],
            'is_green_power': p.get('is_green_power', False), 'pricing_config': p.get('pricing_config', {})},
        'created_by': 'admin', 'created_at': datetime(2026, 7, 15),
        'updated_by': 'admin', 'updated_at': datetime(2026, 7, 15)})
for i in range(min(2, len(all_custs))):
    p = all_pkgs[i % len(all_pkgs)]
    db.retail_contracts.insert_one({'_id': ObjectId(),
        'contract_name': f'{all_custs[i]["short_name"]}-{p["package_name"][:8]}-202601',
        'package_name': p['package_name'], 'package_id': str(p['_id']),
        'customer_name': all_custs[i]['user_name'], 'customer_id': str(all_custs[i]['_id']),
        'purchasing_electricity_quantity': random.uniform(300000, 1000000),
        'purchase_start_month': datetime(2026, 1, 1), 'purchase_end_month': datetime(2026, 6, 30),
        'package_snapshot': {'package_type': p['package_type'], 'model_code': p['model_code'],
            'is_green_power': p.get('is_green_power', False), 'pricing_config': p.get('pricing_config', {})},
        'created_by': 'admin', 'created_at': datetime(2025, 12, 20),
        'updated_by': 'admin', 'updated_at': datetime(2026, 1, 1)})
print(f'  Created {db.retail_contracts.count_documents({})} contracts')

print('=== 6. 分时电价规则 ===')
tl = []
for i in range(96):
    h = i // 4
    if (h == 10) or (h == 11 and (i % 4) == 0): tl.append('尖峰')
    elif (h >= 19 and h < 21) or (h == 21 and (i % 4) == 0): tl.append('尖峰')
    elif (h >= 8 and h < 10) or (h >= 17 and h < 19) or h == 21 or (h == 22 and (i % 4) == 0): tl.append('高峰')
    elif h >= 23 or h < 7 or (h == 7 and (i % 4) == 0): tl.append('低谷')
    else: tl.append('平段')
db.tou_rules.insert_one({'type':'base','version':'V2025-1','name':'2025年江苏省分时电价规则（夏季7月）',
    'months':[7,8],'activation_date':datetime(2025,1,1),'timelines':tl,
    'summer_peak_periods':['尖峰','高峰'],'created_at':datetime(2025,1,1),
    'description':'夏季7-8月：尖峰10:00-11:00,19:00-21:00；高峰08:00-10:00,17:00-19:00,21:00-22:00；低谷23:00-07:00'})
print('  Created TOU rules')

print('=== 7. 国网代购电价 ===')
sgcc_entries = []
for y in [2025, 2026]:
    for m in range(1, 13):
        if y == 2025 and m < 6: continue
        base = 0.42 + random.uniform(-0.05, 0.05)
        mid = f'{y}-{m:02d}'
        sgcc_entries.append({'_id': mid,
            'purchase_price': round(base*1000, 2),
            'avg_on_grid_price': round(base*0.95*1000, 2),
            'purchase_scale_kwh': round(random.uniform(800000, 1200000), 2),
            'historical_deviation_discount': round(random.uniform(-3, 0), 2),
            'network_loss_price': round(random.uniform(20, 30), 2),
            'system_op_cost_discount': round(random.uniform(0, 2), 2),
            'attachment_name': f'{mid}电网代理购电价格公告.pdf',
            'full_data': {'price_composition': [
                ['项目','金额（元/千瓦时）'],
                ['一、代理购电价格', f'{base:.4f}'],
                ['二、输配电价','0.1850'],
                ['三、政府性基金及附加','0.0253'],
                ['四、合计', f'{base+0.2103:.4f}']]},
            'month': mid})
db.price_sgcc.insert_many(sgcc_entries)
print(f'  Created {len(sgcc_entries)} SGCC records')

print('=== 8. 日前现货价格 (31天x96点) ===')
BULK_SIZE = 5000
docs = []
for d in JULY_DATES:
    wk = d.weekday() >= 5
    for i in range(96):
        h, m = i // 4, (i % 4) * 15
        dt, ts = gen_ts(i, d)
        pr = gen_price(h, m, 320 if wk else 350, 60)
        vl = gen_vol(h, m)
        docs.append({'datetime': dt, 'date_str': f'2026-07-{d.day:02d}', 'time_str': ts,
            'total_clearing_power': round(vl,2), 'thermal_clearing_power': round(vl*0.65,2),
            'hydro_clearing_power': round(vl*0.12,2), 'wind_clearing_power': round(vl*0.10,2),
            'solar_clearing_power': round(vl*0.08,2), 'pumped_storage_clearing_power': round(vl*0.03,2),
            'battery_storage_generation': round(vl*0.02,2), 'avg_clearing_price': round(pr,2)})
        if len(docs) >= BULK_SIZE:
            db.day_ahead_spot_price.insert_many(docs); docs = []
if docs: db.day_ahead_spot_price.insert_many(docs)
print(f'  Created {db.day_ahead_spot_price.count_documents({})} records')

print('=== 9. 实时现货价格 (31天x96点) ===')
docs = []
for d in JULY_DATES:
    wk = d.weekday() >= 5
    for i in range(96):
        h, m = i // 4, (i % 4) * 15
        dt, ts = gen_ts(i, d)
        pr = gen_price(h, m, 330 if wk else 365, 100)
        vl = gen_vol(h, m)
        docs.append({'datetime': dt, 'date_str': f'2026-07-{d.day:02d}', 'time_str': ts,
            'total_clearing_power': round(vl,2), 'thermal_clearing_power': round(vl*0.60,2),
            'hydro_clearing_power': round(vl*0.13,2), 'wind_clearing_power': round(vl*0.11,2),
            'solar_clearing_power': round(vl*0.09,2), 'pumped_storage_clearing_power': round(vl*0.04,2),
            'battery_storage_generation': round(vl*0.03,2), 'avg_clearing_price': round(pr,2)})
        if len(docs) >= BULK_SIZE:
            db.real_time_spot_price.insert_many(docs); docs = []
if docs: db.real_time_spot_price.insert_many(docs)
print(f'  Created {db.real_time_spot_price.count_documents({})} records')

print('=== 10. 实际运行数据 (31天x96点) ===')
docs = []
for d in JULY_DATES:
    wk = d.weekday() >= 5
    for i in range(96):
        h, m = i // 4, (i % 4) * 15
        dt, ts = gen_ts(i, d)
        ld = gen_load(h, m, is_weekend=wk)
        docs.append({'datetime': dt, 'date_str': f'2026-07-{d.day:02d}', 'time_str': ts,
            'system_load': round(ld,2), 'tieline_flow': round(random.uniform(5000,8000)*(0.85 if wk else 1.0),2)})
        if len(docs) >= BULK_SIZE:
            db.actual_operation.insert_many(docs); docs = []
if docs: db.actual_operation.insert_many(docs)
print(f'  Created {db.actual_operation.count_documents({})} records')

print('=== 11. 实时发电出力 (31天x96点) ===')
docs = []
for d in JULY_DATES:
    wk = d.weekday() >= 5
    wf = 0.85 if wk else 1.0
    for i in range(96):
        h, m = i // 4, (i % 4) * 15
        dt, ts = gen_ts(i, d)
        docs.append({'datetime': dt, 'date_str': f'2026-07-{d.day:02d}', 'time_str': ts,
            'wind_generation': round(gen_wind(h,m)*wf,2), 'solar_generation': round(gen_solar(h,m)*wf,2),
            'hydro_generation': round(random.uniform(3000,5000)*wf,2),
            'pumped_storage_generation': round(random.uniform(500,1500)*wf,2),
            'battery_storage_generation': round(random.uniform(200,800)*wf,2)})
        if len(docs) >= BULK_SIZE:
            db.real_time_generation.insert_many(docs); docs = []
if docs: db.real_time_generation.insert_many(docs)
print(f'  Created {db.real_time_generation.count_documents({})} records')

print('=== 12. 日前预测数据 (31天x96点) ===')
docs = []
for d in JULY_DATES:
    wk = d.weekday() >= 5
    for i in range(96):
        h, m = i // 4, (i % 4) * 15
        dt, ts = gen_ts(i, d)
        docs.append({'datetime': dt, 'date_str': f'2026-07-{d.day:02d}', 'time_str': ts,
            'system_load_forecast': round(gen_load(h,m,is_weekend=wk)*random.uniform(0.95,1.05),2),
            'wind_forecast': round(gen_wind(h,m)*random.uniform(0.9,1.1),2),
            'pv_forecast': round(gen_solar(h,m)*random.uniform(0.9,1.1),2),
            'nonmarket_unit_forecast': round(random.uniform(8000,12000),2),
            'tieline_plan': round(random.uniform(5000,8000)*(0.85 if wk else 1.0),2)})
        if len(docs) >= BULK_SIZE:
            db.daily_release.insert_many(docs); docs = []
if docs: db.daily_release.insert_many(docs)
print(f'  Created {db.daily_release.count_documents({})} records')

print('=== 13. 用户负荷数据 (7用户x31天x96点) ===')
USERS = [('user_001','华兴科技','MTR_001_A',3500),('user_002','南钢集团','MTR_002_A',8500),
         ('user_003','威孚高科','MTR_003_A',2800),('user_004','天合光能','MTR_004_A',5200),
         ('user_005','徐工集团','MTR_005_A',4800),('user_006','南通醋纤','MTR_006_A',2200),
         ('user_007','亚星客车','MTR_007_A',1800)]
docs = []
for uid, un, mid, bl in USERS:
    for d in JULY_DATES:
        wk = d.weekday() >= 5
        wf = 0.6 if wk else 1.0
        for i in range(96):
            dt, ts = gen_ts(i, d)
            tf = math.sin((i/96)*2*math.pi - math.pi/2)
            mp = bl*0.15*math.sin((i-28)/8*math.pi) if 28<=i<=36 else 0
            ep = bl*0.25*math.sin((i-68)/12*math.pi) if 68<=i<=80 else 0
            lv = max(bl*0.3, min(bl*1.6, (bl+bl*0.3*tf+mp+ep)*wf+random.uniform(-bl*0.05,bl*0.05)))
            docs.append({'timestamp': dt, 'user_id': uid, 'user_name': un, 'meter_id': mid,
                'load_value': round(lv,2), 'time_str': ts, 'date_str': f'2026-07-{d.day:02d}'})
            if len(docs) >= BULK_SIZE:
                db.user_load_data.insert_many(docs); docs = []
if docs: db.user_load_data.insert_many(docs)
print(f'  Created {db.user_load_data.count_documents({})} records')

print('=== 14. 短期负荷预测 ===')
docs = []
for d in JULY_DATES:
    for da in [1,2,3]:
        for i in range(96):
            dt, _ = gen_ts(i, d)
            tf = math.sin((i/96)*2*math.pi - math.pi/2)
            nz = random.uniform(-1000,1000)*(da*0.5)
            fv = max(15000, min(60000, 35000+35000*0.3*tf+nz))
            docs.append({'forecast_date': datetime(2026,7,d.day), 'forecast_type': f'd+{da}',
                'datetime': dt, 'forecast_value': round(fv,2), 'created_at': datetime(2026,7,d.day,12)})
            if len(docs) >= BULK_SIZE:
                db.short_term_load_forecast.insert_many(docs); docs = []
if docs: db.short_term_load_forecast.insert_many(docs)
print(f'  Created {db.short_term_load_forecast.count_documents({})} records')

print('=== 15. 预测准确度 ===')
docs = []
for d in JULY_DATES:
    docs.append({'forecast_date': datetime(2026,7,d.day), 'forecast_type': 'd+1',
        'mape': round(random.uniform(1.5,4.5),2), 'rmse': round(random.uniform(200,600),2),
        'mae': round(random.uniform(150,400),2), 'sample_count': 96,
        'created_at': datetime(2026,7,d.day,12)})
    docs.append({'forecast_date': datetime(2026,7,d.day), 'forecast_type': 'd+2',
        'mape': round(random.uniform(2.5,6.0),2), 'rmse': round(random.uniform(300,800),2),
        'mae': round(random.uniform(200,600),2), 'sample_count': 96,
        'created_at': datetime(2026,7,d.day,12)})
db.forecast_accuracy_daily.insert_many(docs)
print(f'  Created {len(docs)} accuracy records')

print('=== 16. 周预测数据 ===')
docs = []
for w in range(1, 6):
    ws = datetime(2026, 7, 1) + timedelta(weeks=w-1)
    for di in range(7):
        dd = ws + timedelta(days=di)
        if dd.month != 7: continue
        for i in range(96):
            h, m = i // 4, (i % 4) * 15
            dt = dd.replace(hour=h, minute=m) if not (h==23 and m>=45) else dd+timedelta(days=1)
            wk_flag = dt.weekday() >= 5
            docs.append({'week_start': ws, 'datetime': dt,
                'system_load_forecast': round(gen_load(h,m,is_weekend=wk_flag)*random.uniform(0.97,1.03),2),
                'wind_forecast': round(gen_wind(h,m)*random.uniform(0.9,1.1),2),
                'pv_forecast': round(gen_solar(h,m)*random.uniform(0.9,1.1),2),
                'temperature': round(random.uniform(28,38),1), 'humidity': round(random.uniform(60,90),1)})
db.weekly_forecast.insert_many(docs)
print(f'  Created {len(docs)} weekly forecast records')

print('=== 17. 价格预测结果 ===')
docs = []
for d in JULY_DATES:
    wk = d.weekday() >= 5
    bp = 330 if wk else 360
    for i in range(96):
        h, m = i // 4, (i % 4) * 15
        dt, ts = gen_ts(i, d)
        ap = gen_price(h, m, bp, 70)
        docs.append({'date': f'2026-07-{d.day:02d}', 'time_str': ts, 'datetime': dt,
            'actual_price': round(ap,2), 'd2_forecast': round(ap+random.uniform(-30,30),2),
            'da_forecast': round(ap+random.uniform(-15,15),2)})
db.price_forecast_results.insert_many(docs)
print(f'  Created {len(docs)} price forecast records')

print('=== 18. 中长期交易复盘 ===')
REVIEWS = [
    ('2026年7月中长期交易复盘','月度',datetime(2026,7,1),'7月江苏省中长期电力交易市场运行平稳，双边协商交易均价368.5元/MWh。'),
    ('2026年6月中长期交易复盘','月度',datetime(2026,6,1),'6月迎峰度夏前市场交易活跃，月度集中竞价成交量环比增长15%。'),
    ('2026年Q2中长期交易复盘','季度',datetime(2026,4,1),'二季度省内市场化交易电量累计580亿千瓦时，同比增长8.2%。'),
    ('2026年5月中长期交易复盘','月度',datetime(2026,5,1),'5月气温偏高，用电负荷增长明显，中长期合约均价略有上浮。'),
    ('2026年7月第1周交易复盘','周度',datetime(2026,7,7),'本周省内用电负荷持续攀升，最高负荷达9850万千瓦。'),
    ('2026年7月第2周交易复盘','周度',datetime(2026,7,14),'高温持续，电网负荷创新高，现货市场价格波动加剧。'),
    ('2026年7月第3周交易复盘','周度',datetime(2026,7,21),'台风影响，新能源出力波动较大，日前价格预测偏差增加。'),
]
for t, p, rd, c in REVIEWS:
    db.medium_long_term_reviews.insert_one({'_id': ObjectId(), 'review_title': t,
        'review_period': p, 'review_date': rd, 'content': c,
        'created_by': 'admin', 'created_at': datetime(2026, 7, 31)})
print(f'  Created {len(REVIEWS)} reviews')

print('=== 19. 月度交易策略 ===')
STRATS = [
    ('7月月度双边协商策略','2026-07','bilateral',500000,380,'executed'),
    ('7月月度集中竞价策略','2026-07','centralized_auction',200000,370,'executed'),
    ('8月月度双边协商策略','2026-08','bilateral',550000,385,'draft'),
    ('6月月度双边协商策略','2026-06','bilateral',480000,375,'executed'),
]
for sn, m, st, tv, pl, ss in STRATS:
    db.monthly_trading_strategies.insert_one({'_id': ObjectId(), 'strategy_name': sn,
        'month': m, 'strategy_type': st, 'target_volume': tv, 'price_limit': pl,
        'status': ss, 'created_by': 'admin', 'created_at': datetime(2026,6,15),
        'updated_at': datetime(2026,7,1)})
print(f'  Created {len(STRATS)} strategies')

print('=== 20. D2交易策略 ===')
docs = []
for d in JULY_DATES[:15]:
    for dr in ['buy','sell']:
        docs.append({'_id': ObjectId(), 'date': f'2026-07-{d.day:02d}', 'direction': dr,
            'target_volume': round(random.uniform(5000,30000),2),
            'expected_price': round(random.uniform(300,450),2),
            'status': random.choice(['executed','pending']),
            'created_at': datetime(2026,7,d.day), 'updated_at': datetime(2026,7,d.day),
            'created_by': 'admin'})
db.d2_trading_strategies.insert_many(docs)
print(f'  Created {len(docs)} D2 strategies')

print('=== 21. 合同曲线 ===')
docs = []
ac = list(db.customers.find({'status': 'active'}))
for cust in ac[:5]:
    for d in JULY_DATES[:7]:
        for h in range(24):
            docs.append({'_id': ObjectId(), 'customer_id': str(cust['_id']),
                'customer_name': cust['user_name'], 'date': f'2026-07-{d.day:02d}',
                'hour': h, 'contracted_volume': round(random.uniform(100,500),2),
                'executed_volume': round(random.uniform(80,480),2),
                'deviation': round(random.uniform(-50,50),2),
                'created_at': datetime(2026,7,d.day)})
db.contract_curves.insert_many(docs)
print(f'  Created {len(docs)} contract curves')

print('=== 22. 中长期负荷预测 ===')
docs = []
for m in range(7, 13):
    bm = random.uniform(25000, 35000)
    for d in range(1, 29, 7):
        docs.append({'_id': ObjectId(), 'forecast_month': f'2026-{m:02d}',
            'forecast_date': datetime(2026, m, d),
            'forecast_value': round(bm+random.uniform(-2000,2000),2),
            'created_at': datetime(2026, 6, 15)})
db.medium_long_term_load_forecast.insert_many(docs)
print(f'  Created {len(docs)} MLF records')

print('=== 23. RPA监控数据 ===')
TC = [
    ('日前申报数据抓取','data_collection','09:00',True,datetime(2026,7,30,9,0),'success'),
    ('实时市场数据监控','monitoring','continuous',True,datetime(2026,7,30,10,30),'running'),
    ('清算数据自动对账','settlement','18:00',True,datetime(2026,7,29,18,0),'success'),
    ('电网运行数据采集','data_collection','every 15min',True,datetime(2026,7,30,10,15),'success'),
]
for tn, tt, sc, en, lr, ss in TC:
    db.task_configs.insert_one({'_id': ObjectId(), 'name': tn, 'task_name': tn, 'task_type': tt,
        'schedule': sc, 'enabled': en, 'last_run': lr, 'status': ss})
docs = []
for d in JULY_DATES[:10]:
    for tn, tt, _, _, _, _ in TC[:3]:
        st = random.choice(['success','success','success','failed'])
        docs.append({'_id': ObjectId(), 'task_name': tn, 'task_type': tt,
            'execution_time': datetime(2026,7,d.day,random.randint(8,20),random.randint(0,59)),
            'status': st, 'duration_seconds': round(random.uniform(10,300),1),
            'error_message': '连接超时' if st == 'failed' else None,
            'created_at': datetime(2026,7,d.day)})
db.task_execution_logs.insert_many(docs)
RR = [
    ('日前申报数据抓取',datetime(2026,7,25,9,0),2,datetime(2026,7,25,9,5),'resolved'),
    ('清算数据自动对账',datetime(2026,7,20,18,0),1,datetime(2026,7,20,18,2),'resolved'),
]
for tn, ft, rc, lr, ss in RR:
    db.task_retry_requests.insert_one({'_id': ObjectId(), 'task_name': tn,
        'failure_time': ft, 'retry_count': rc, 'last_retry': lr, 'status': ss})
print('  Created RPA data')

print('=== 24. 日报数据 ===')
docs = []
for d in JULY_DATES[:20]:
    docs.append({'_id': ObjectId(), 'report_date': f'2026-07-{d.day:02d}',
        'title': f'2026年7月{d.day}日电力市场日报',
        'summary': f'7月{d.day}日，江苏电网最高负荷{random.randint(9000,10500)}万千瓦，日前均价{random.randint(320,420)}元/MWh。',
        'created_at': datetime(2026,7,d.day,18)})
db.daily_reports.insert_many(docs)
print(f'  Created {len(docs)} daily reports')

print('=== 25. 月度价格趋势 ===')
TRENDS = [
    ('2026-01',385.5,392.3,650.2,180.5), ('2026-02',372.8,378.1,620.0,175.2),
    ('2026-03',358.2,365.5,580.6,165.8), ('2026-04',342.6,348.9,550.3,155.4),
    ('2026-05',365.4,372.8,620.8,170.1), ('2026-06',398.7,408.2,720.5,195.6),
    ('2026-07',412.3,425.6,780.0,210.3),
]
for m, da, rt, mx, mn in TRENDS:
    db.monthly_price_trends.insert_one({'_id': ObjectId(), 'month': m,
        'avg_da_price': da, 'avg_rt_price': rt, 'max_price': mx, 'min_price': mn})
print(f'  Created {len(TRENDS)} price trends')

print('\n=== 创建索引 ===')
for c, keys in [('user_load_data',[('timestamp',1),('user_id',1)]),
    ('day_ahead_spot_price',[('date_str',1),('datetime',1)]),
    ('real_time_spot_price',[('date_str',1),('datetime',1)]),
    ('actual_operation',[('date_str',1)]),('real_time_generation',[('date_str',1)]),
    ('daily_release',[('date_str',1)]),('short_term_load_forecast',[('forecast_date',1)]),
    ('price_forecast_results',[('date',1)]),('customers',[('status',1)]),
    ('retail_contracts',[('customer_id',1)]),('retail_packages',[('status',1)])]:
    try: db[c].create_index(keys)
    except: pass

print('\n' + '='*60)
print('全业务数据初始化完成！')
print('='*60)
print(f'\n集合统计:')
for c in sorted(db.list_collection_names()):
    cnt = db[c].count_documents({})
    if cnt > 0:
        print(f'  {c}: {cnt} 条')