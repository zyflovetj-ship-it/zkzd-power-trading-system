# NOTE: CustomPrices 类已经在重构中删除
# 这个文件中的 validate_price_ratio 方法已经被 pricing_model_service.py 中的新校验逻辑替代

from typing import Any, Dict


class PricingEngine:
    """Retail package pricing calculation engine."""

    STANDARD_RATIOS = {
        "peak_to_flat": 1.8,      # 尖峰/平 = 1.8 (上浮80%)
        "high_to_flat": 1.6,      # 峰/平 = 1.6
        "valley_to_flat": 0.4,    # 谷/平 = 0.4
        "deep_valley_to_flat": 0.3  # 深谷/平 = 0.3 (下浮70%)
    }

    @staticmethod
    def _base_price(package: dict) -> float:
        """从套餐对象中提取基准电价（元/MWh），缺省回退到 400。"""
        for key in ("base_price", "fixed_price", "linked_price", "price"):
            val = package.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue
        return 400.0

    @staticmethod
    def calculate_fixed_linked_price(package: dict, date: str, time_period: str, volume_mwh: float):
        """
        固定联动电价试算（旧口径，保留兼容）。

        按标准时段比价（尖峰/峰/平/谷/深谷）由基准价推导各时段价格，
        并以平段价 × 电量估算总费用。
        """
        base = PricingEngine._base_price(package)
        r = PricingEngine.STANDARD_RATIOS
        flat = round(base, 2)
        peak = round(base * r["peak_to_flat"], 2)
        high = round(base * r["high_to_flat"], 2)
        valley = round(base * r["valley_to_flat"], 2)
        deep = round(base * r["deep_valley_to_flat"], 2)
        vol = float(volume_mwh or 0)
        total = round(flat * vol, 2)
        return {
            "package_id": package.get("package_id") or str(package.get("_id", "")),
            "date": date,
            "time_period": time_period,
            "volume_mwh": volume_mwh,
            "pricing_mode": "fixed_linked",
            "flat_price": flat,
            "peak_price": peak,
            "high_price": high,
            "valley_price": valley,
            "deep_valley_price": deep,
            "total_cost": total,
            "currency": "CNY",
        }

    @staticmethod
    def calculate_price_spread_price(package: dict, date: str, time_period: str, volume_mwh: float):
        """
        价差联动电价试算（旧口径，保留兼容）。

        以基准价 ×（1 + 价差比例）得到联动价，并估算总费用。
        """
        base = PricingEngine._base_price(package)
        spread_ratio = float(package.get("spread_ratio") or 0.05)
        linked = round(base * (1 + spread_ratio), 2)
        vol = float(volume_mwh or 0)
        total = round(linked * vol, 2)
        return {
            "package_id": package.get("package_id") or str(package.get("_id", "")),
            "date": date,
            "time_period": time_period,
            "volume_mwh": volume_mwh,
            "pricing_mode": "price_spread",
            "base_price": round(base, 2),
            "linked_price": linked,
            "spread_ratio": spread_ratio,
            "total_cost": total,
            "currency": "CNY",
        }

    # =====================================================================
    # 江苏 2027 新规零售套餐测算（口径对齐《套餐测算模板 新v2》）
    # =====================================================================
    @staticmethod
    def calculate_jiangsu_2027_pointwise(
        params: Dict[str, Any],
        points: Dict[str, Any],
        market: Dict[str, Any],
    ) -> Dict[str, Any]:
        """江苏 2027 新规 —— 逐点卷积模式（严格对齐《套餐测算模板-新v2.xlsx》峰谷时段表/分时）。

        与三段聚合版(calculate_jiangsu_2027)的区别：本方法按 24/96 个时段点逐点计价，
        每个点的"平段基准"用该点批发分时价，峰/谷用平段加权均价×系数封顶/托底，最后按电量加权。

        points 输入：
          labels:       ["谷","平","峰",...] 每点时段标签
          curve:        [电量/权重,...]       每点电量或用电曲线权重（用于加权，总和>0）
          wholesale:    [元/MWh,...]          每点批发市场分时价（已含中长期/日前/实时合成）
          max_pnt:      [元/MWh,...] 可选      每点 max(各市场价格) 用于零售参考价；缺省用 wholesale
        market 输入：
          wholesale_price  月度批发价（T4，用于封顶价）
          share_cost_compensation/share_imbalance/share_market_adjust 三类分摊（T5/T6/T7）
        params 同 calculate_jiangsu_2027。

        返回结构与三段版兼容（prices/share/energy_avg_price/cap_price/settle_price/sell_price 等）。
        """
        labels = list(points.get("labels") or [])
        curve = [float(x or 0.0) for x in (points.get("curve") or [])]
        wholesale = [float(x or 0.0) for x in (points.get("wholesale") or [])]
        max_pnt = points.get("max_pnt")
        n = len(labels)
        if n == 0 or len(curve) != n or len(wholesale) != n:
            raise ValueError("pointwise: labels/curve/wholesale 长度不一致或为空")
        curve_sum = sum(curve)
        if curve_sum <= 0:
            raise ValueError("pointwise: curve 电量合计为 0")

        # ---- 参数 ----
        sf = params.get("service_fee")
        service_fee = float(sf) if sf is not None else float(params.get("kp", 0.002)) * 1000.0
        peak_coef = float(params.get("peak_coef", 1.6))
        valley_coef = float(params.get("valley_coef", 0.4))
        f_ratio = float(params.get("f_ratio", 0.05))
        k1 = float(params.get("k1_share", 1.0))
        k2 = float(params.get("k2_share", 1.0))
        k3 = float(params.get("k3_share", 1.0))

        # ---- 分摊（T5/T6/T7 -> T8 合计 / T9 零售套餐分摊）----
        cc = float(market.get("share_cost_compensation") or 0.0)
        imb = float(market.get("share_imbalance") or 0.0)
        ma = float(market.get("share_market_adjust") or 0.0)
        if market.get("share_cost_compensation") is None and market.get("share_imbalance") is None and market.get("share_market_adjust") is None:
            cc = float(market.get("share_price") or 0.0)
            imb = 0.0
            ma = 0.0
        share_total = round(cc + imb + ma, 3)              # T8
        share_retail = round(k1 * cc + k2 * imb + k3 * ma, 3)  # T9

        # ---- 平段加权均价 flat_base（模板 分时!B59 用平段电量加权批发价）----
        num = 0.0
        den = 0.0
        for i in range(n):
            if labels[i] == "平":
                num += curve[i] * wholesale[i]
                den += curve[i]
        flat_base = (num / den) if den > 0 else (sum(wholesale) / n)

        # ---- 逐点 Pt（模板 分时!B59）----
        pt = []
        for i in range(n):
            base = wholesale[i] + service_fee + share_retail
            if labels[i] == "谷":
                pt.append(round(min(flat_base * valley_coef, base), 3))
            elif labels[i] == "峰":
                pt.append(round(max(flat_base * peak_coef, base), 3))
            else:
                pt.append(round(base, 3))

        # ---- 用户电价 T10 = Σ(curve×Pt)/Σcurve ----
        energy_avg = round(sum(curve[i] * pt[i] for i in range(n)) / curve_sum, 3)

        # ---- 零售参考价 T2 = Σ(curve×max_pnt)/Σcurve ----
        ref_series = max_pnt if (max_pnt and len(max_pnt) == n) else wholesale
        reference = round(sum(curve[i] * float(ref_series[i] or 0.0) for i in range(n)) / curve_sum, 3)

        # ---- 封顶价 T3 = T2 + T8 + (T4-T8)×F ----
        wholesale_price = float(market.get("wholesale_price") or 0.0)
        cap_price = round(reference + share_total + (wholesale_price - share_total) * f_ratio, 3)

        # ---- 非分时 T11 = T4 + 服务费 + (T9-T8) ----
        non_tou = round(wholesale_price + service_fee + (share_retail - share_total), 3)

        capped = energy_avg > cap_price
        settle_price = min(energy_avg, cap_price)
        settle_non_tou = min(non_tou, cap_price)

        # ---- 绿电环境价值 ----
        green_mode = params.get("green_mode") or "否"
        ev = params.get("env_value")
        env_value = float(ev) if ev is not None else 30.0
        green_add = env_value if green_mode in ("普通绿电", "小时级绿电") else 0.0
        sell_price = round(settle_price + green_add, 3)

        # 分时段均价（用于展示，按标签聚合 Pt 加权）
        seg = {"峰": [0.0, 0.0], "平": [0.0, 0.0], "谷": [0.0, 0.0]}
        for i in range(n):
            k = labels[i] if labels[i] in seg else "平"
            seg[k][0] += curve[i] * pt[i]
            seg[k][1] += curve[i]
        def seg_avg(k):
            return round(seg[k][0] / seg[k][1], 3) if seg[k][1] > 0 else 0.0

        return {
            "pricing_mode": "jiangsu_2027_pointwise",
            "total_mwh": round(curve_sum, 4),
            "prices": {
                "wholesale_price": round(wholesale_price, 3),
                "flat_base_price": round(flat_base, 3),
                "service_fee": round(service_fee, 3),
                "reference_price": reference,
                "flat_price": seg_avg("平"),
                "peak_price": seg_avg("峰"),
                "valley_price": seg_avg("谷"),
            },
            "share": {
                "cost_compensation": round(cc, 3),
                "imbalance": round(imb, 3),
                "market_adjust": round(ma, 3),
                "total": share_total,
                "retail": share_retail,
                "k1": k1, "k2": k2, "k3": k3,
            },
            "energy_avg_price": energy_avg,   # T10 用户电价
            "cap_price": cap_price,           # T3 封顶价
            "capped": capped,
            "settle_price": round(settle_price, 3),       # T12 最终电价(分时)
            "settle_price_non_tou": settle_non_tou,       # T13 非分时最终
            "non_tou_price": non_tou,                     # T11
            "green_mode": green_mode,
            "green_add": round(green_add, 2),
            "sell_price": sell_price,
            "total_cost": round(sell_price * curve_sum, 2),
            "currency": "CNY",
        }

    @staticmethod
    def calculate_jiangsu_2027(
        params: Dict[str, Any],
        volumes: Dict[str, Any],
        market: Dict[str, Any],
    ) -> Dict[str, Any]:
        """江苏 2027 新规零售套餐测算，核算口径严格对齐《套餐测算模板-新v2.xlsx》。

        模板计价链（峰谷时段表 / 分时!B59）：
          平段加权均价 P_flat_base = Σ(平段电量×批发分时价) / Σ平段电量
          平价 = P_flat_base + 服务费 + 零售套餐分摊
          峰价 = MAX(P_flat_base × 峰段浮动系数, 平价)
          谷价 = MIN(P_flat_base × 谷段浮动系数, 平价)
          用户电价 = 各时段电量加权平均（模板 T10）
          零售套餐分摊 = K1×成本补偿分摊 + K2×不平衡费用分摊 + K3×市场调节分摊（模板 T9）
          分摊合计     = 成本补偿 + 不平衡费用 + 市场调节（模板 T8）
          封顶价       = 零售参考价 + 分摊合计 + (批发价 − 分摊合计) × F（模板 T3）
          最终电价     = MIN(用户电价, 封顶价)（模板 T12）
          绿电环境价值 = 独立叠加（模板 T14，默认 30 元/MWh）

        参数 params:
          peak_coef   峰段浮动系数，默认 1.6（≥1.6，上浮≥60%）
          valley_coef 谷段浮动系数，默认 0.4（≤0.4，下浮≥60%）
          service_fee 服务费，元/MWh，默认 2.0（≈kP 0.002 元/kWh×1000）
          f_ratio     F 系数，默认 0.05
          k1_share/k2_share/k3_share  K1/K2/K3 分摊比例，默认 1/1/1（均 100%）
          include_share_in_base  平段价是否含零售套餐分摊（模板=True）
          green_mode  "否"/"普通绿电"/"小时级绿电"
          env_value   绿电环境价值，元/MWh，默认 30
        行情 market:
          wholesale_price        月度批发价（用于封顶，模板 T4）
          flat_base_price        平段加权均价（用于分时定价，缺省=wholesale_price）
          reference_price        零售参考价（缺省=wholesale_price）
          share_cost_compensation/share_imbalance/share_market_adjust 三类分摊（元/MWh）
          share_price            （兼容）单一分摊，未给三类时生效
        电量 volumes: peak_mwh / flat_mwh / valley_mwh（MWh）
        """
        # ---- 行情与分摊 ----
        wholesale = float(market.get("wholesale_price") or 0.0)
        fbb = market.get("flat_base_price")
        flat_base = float(fbb) if fbb is not None else wholesale
        ref = market.get("reference_price")
        reference = float(ref) if ref is not None else wholesale

        cc = market.get("share_cost_compensation")
        imb = market.get("share_imbalance")
        ma = market.get("share_market_adjust")
        if cc is None and imb is None and ma is None:
            cc, imb, ma = float(market.get("share_price") or 0.0), 0.0, 0.0
        else:
            cc, imb, ma = float(cc or 0.0), float(imb or 0.0), float(ma or 0.0)
        share_total = cc + imb + ma

        # ---- 参数 ----
        peak_coef = float(params.get("peak_coef", 1.6))
        valley_coef = float(params.get("valley_coef", 0.4))
        sf = params.get("service_fee")
        service_fee = float(sf) if sf is not None else float(params.get("kp", 0.002)) * 1000.0
        f_ratio = float(params.get("f_ratio", 0.05))
        k1 = float(params.get("k1_share", 1.0))
        k2 = float(params.get("k2_share", 1.0))
        k3 = float(params.get("k3_share", 1.0))
        include_share = bool(params.get("include_share_in_base", True))

        share_retail = k1 * cc + k2 * imb + k3 * ma

        # ---- 分时电价（模板 分时!B59 的周期级等价实现）----
        flat_price = flat_base + service_fee + (share_retail if include_share else 0.0)
        peak_price = max(flat_base * peak_coef, flat_price)
        valley_price = min(flat_base * valley_coef, flat_price)

        qp = float(volumes.get("peak_mwh") or 0.0)
        qf = float(volumes.get("flat_mwh") or 0.0)
        qv = float(volumes.get("valley_mwh") or 0.0)
        total = qp + qf + qv

        energy_fee = qp * peak_price + qf * flat_price + qv * valley_price
        energy_avg = (energy_fee / total) if total > 0 else 0.0   # 用户电价 T10

        # ---- 封顶价与封顶结算（模板 T3 / T12）----
        cap_price = reference + share_total + (wholesale - share_total) * f_ratio
        capped = total > 0 and energy_avg > cap_price
        settle_price = min(energy_avg, cap_price) if total > 0 else 0.0

        # ---- 绿电环境价值（独立叠加，模板 T14）----
        green_mode = params.get("green_mode") or "否"
        env_value = params.get("env_value")
        env_value = float(env_value) if env_value is not None else 30.0
        green_add = env_value if green_mode in ("普通绿电", "小时级绿电") else 0.0

        sell_price = settle_price + green_add
        total_cost = round(sell_price * total, 2)

        return {
            "pricing_mode": "jiangsu_2027",
            "total_mwh": round(total, 4),
            "volumes": {
                "peak_mwh": round(qp, 4),
                "flat_mwh": round(qf, 4),
                "valley_mwh": round(qv, 4),
            },
            "prices": {
                "wholesale_price": round(wholesale, 3),
                "flat_base_price": round(flat_base, 3),
                "service_fee": round(service_fee, 3),
                "reference_price": round(reference, 3),
                "flat_price": round(flat_price, 3),
                "peak_price": round(peak_price, 3),
                "valley_price": round(valley_price, 3),
            },
            "share": {
                "cost_compensation": round(cc, 3),
                "imbalance": round(imb, 3),
                "market_adjust": round(ma, 3),
                "total": round(share_total, 3),
                "retail": round(share_retail, 3),
                "k1": k1, "k2": k2, "k3": k3,
            },
            "energy_fee": round(energy_fee, 2),
            "energy_avg_price": round(energy_avg, 3),   # 用户电价
            "cap_price": round(cap_price, 3),
            "capped": capped,
            "settle_price": round(settle_price, 3),      # 最终电价
            "green_mode": green_mode,
            "green_add": round(green_add, 2),
            "sell_price": round(sell_price, 3),
            "total_cost": total_cost,
            "currency": "CNY",
        }
