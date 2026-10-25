# NOTE: CustomPrices 类已经在重构中删除
# 这个文件中的 validate_price_ratio 方法已经被 pricing_model_service.py 中的新校验逻辑替代

class PricingEngine:
    """Retail package pricing calculation engine."""

    STANDARD_RATIOS = {
        "peak_to_flat": 1.8,      # 尖峰/平 = 1.8 (上浮80%)
        "high_to_flat": 1.6,      # 峰/平 = 1.6
        "valley_to_flat": 0.4,    # 谷/平 = 0.4
        "deep_valley_to_flat": 0.3  # 深谷/平 = 0.3 (下浮70%)
    }

    # NOTE: 此方法已废弃，使用 pricing_model_service.validate_pricing_config 替代
    # @staticmethod
    # def validate_price_ratio(custom_prices: CustomPrices) -> dict:
    #     """Validate if the price ratio complies with regulations."""
    #     pass

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
        固定联动电价试算。

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
        价差联动电价试算。

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

