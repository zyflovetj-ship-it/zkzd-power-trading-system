# zkzd电力交易系统

电力交易辅助决策平台，覆盖客户/合同/套餐管理、负荷与价格预测、交易策略决策、
风险管理、结算对账、客户聚类、系统管理等业务能力。

---

## 1. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python + FastAPI + MongoDB + JWT（OAuth2 密码模式） |
| 前端 | Vite 6 + React 19 + TypeScript + Ant Design v5 + ECharts |
| 部署 | Docker Compose（frontend / backend / mongo） |

## 2. 目录结构

```
webapp/         后端
  api/            路由层（全局前缀 /api/v1）
  services/       业务逻辑
  models/         Pydantic 模型
  scripts/        数据初始化与自测脚本
  tools/          MongoDB 连接、鉴权等基础工具
  tasks/          定时任务注册与实现
web/            前端（Vite + React 19 + AntD，当前默认前端）
frontend/       遗留前端（CRA + MUI，仅作对照，不参与部署）
docker-compose.yml
```

## 3. 部署（Docker Compose）

```bash
docker compose up -d --build      # 构建并后台启动
docker compose logs -f backend    # 查看后端日志
docker compose down               # 停止并移除容器
```

| 服务 | 宿主机端口 | 说明 |
|---|---|---|
| frontend | 8080 | nginx 托管前端产物，`/api` 反代到后端 |
| backend | 8007 → 容器 8005 | FastAPI + uvicorn |
| mongo | 127.0.0.1:27018 → 容器 27017 | MongoDB 7，数据卷 `mongo_data` |

访问：前端 `http://<host>:8080`，接口文档 `http://<host>:8007/docs`。

> 前端镜像使用 `npm ci` 严格按 `package-lock.json` 安装依赖，
> 避免 `npm install` 按 `^` 范围解析最新版导致的构建不可重现。

## 4. 本地开发

```bash
# 后端
cd webapp
uvicorn webapp.main:app --reload --port 8005

# 前端
cd web
npm install
npm run dev
```

## 5. 数据初始化

### 5.1 生成基础数据

```bash
cd webapp
python -m scripts.init_spot_price_data                     # 90 天日前/实时电价（96 点/日）
python -m scripts.init_actual_load_data                    # 90 天实际负荷（96 点/日）
python -m scripts.init_short_term_load_forecast_mock_data  # 短期负荷预测（d+1）
python -m scripts.init_rpa_settlement_data                 # RPA 计量读数（96 点/日）
python -m scripts.init_risk_collections                    # 风险域集合、索引与默认限额
```

### 5.2 生成 48 点曲线

结算与校验依赖两条 48 点曲线，由数据校验接口从上面的 96 点源数据聚合生成：

```bash
# 手工负荷曲线：user_load_data -> load_curve_user
POST /api/v1/data-validation/transform-manual-data
     {"import_batch_id": "SIM_LOAD_2026_10"}

# 结算曲线：rpa_load_data -> settlement_curve_user
POST /api/v1/data-validation/import-rpa-data
     {"rpa_batch_id": "SIM_RPA_2026_10", "source_collection": "rpa_load_data"}
```

### 5.3 定价主数据

零售结算、利润分析、持仓合约的均价依赖套餐定价配置：

- `pricing_models`：定价模型定义（`fixed_linked_fee_non_time` 等）
- `retail_packages.pricing_config`：`fixed_price_value`（元/kWh）、`linked_ratio`
- `retail_contracts.package_snapshot`：合同签约时的定价快照

固定价需落在 463 号文浮动区间 `[0.33144, 0.49716]` 元/kWh
（基准价 0.4143 × [0.8, 1.2]），可由 `PricingModelService.validate_pricing_config()` 校验。

## 6. 单位口径（重要，改动前必读）

| 数据 | 单位 | 换算 |
|---|---|---|
| `user_load_data.value` | 15 分钟平均功率 **kW** | 时段电量 = `value × 0.25h` |
| `short_term_load_forecast.value` | 15 分钟平均功率 **kW** | 同上 |
| `rpa_load_data.load_kw` | 15 分钟平均功率 **kW** | 同上 |
| `load_curve_user.load_kwh` | 30 分钟时段电量 **kWh** | 已换算，直接使用 |
| `settlement_curve_user.load_kwh` | 30 分钟时段电量 **kWh** | 已换算，直接使用 |
| 电价（`day_ahead_spot_price.value` 等） | **元/MWh** | — |

- 把功率当电量累加会使电量与金额**虚高 4 倍**（历史缺陷，已修）。
- 业务日约定：24:00 存为**次日 00:00**，归属前一日；取某日曲线用左开右闭区间。

## 7. MongoDB 索引管理

零售套餐等模块有独立的索引创建脚本（幂等，可重复执行）：

```bash
node webapp/scripts/create_retail_package_indexes.js
```

其中 `package_name` 唯一索引用于保证套餐名称唯一性。
风险域索引由 `scripts.init_risk_collections` 创建。

## 8. 自测

```bash
cd webapp
python -m scripts.selfcheck_risk_engine   # 风险引擎口径自测（32 项）
python -m scripts.selfcheck_risk_p1       # 回测/压力测试自测（23 项）
```

## 9. 遗留说明

`frontend/` 为旧版 CRA + MUI 前端，仅作对照保留，**不参与部署**。
旧版技术文档与开发规范已归档，不在本库维护。
