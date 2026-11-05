"""零售套餐合规校验（江苏 2027 新规 / 附件2）。

校验项（附件2 零售套餐参数）：
  1. 峰段系数 ≥ 1.6（上浮 ≥60%）
  2. 谷段系数 ≤ 0.4（下浮 ≥60%）
  3. 售电服务费（P浮动）2 ~ 20 元/MWh（越界即提示，法定代表人再次确认）
  4. F 系数 0 ~ 5%
  5. K分摊1 = 100%
  6. K分摊2 70% ~ 100%
  7. K分摊3 0% ~ 100%
  8. 绿电：若参与绿电，环境价值应 > 0

越界即触发「风险预警」，按《江苏电力交易工作指引》第五条须经法定代表人确认。
"""
from typing import Any, Dict, List, Optional

#: 规则定义（供前端展示与后端校验共用）
RULES: List[Dict[str, Any]] = [
    {"key": "peak_coef", "name": "峰段系数", "min": 1.6, "max": None, "unit": "",
     "rule": "≥1.6（上浮≥60%）", "ref": "附件2 第1项"},
    {"key": "valley_coef", "name": "谷段系数", "min": None, "max": 0.4, "unit": "",
     "rule": "≤0.4（下浮≥60%）", "ref": "附件2 第1项"},
    {"key": "service_fee", "name": "售电服务费（P浮动）", "min": 2.0, "max": 20.0, "unit": "元/MWh",
     "rule": "2 ~ 20 元/MWh", "ref": "附件2 第2项"},
    {"key": "f_ratio", "name": "F 系数", "min": 0.0, "max": 0.05, "unit": "",
     "rule": "0 ~ 5%", "ref": "附件2"},
    {"key": "k1_share", "name": "K分摊1", "min": 1.0, "max": 1.0, "unit": "",
     "rule": "= 100%", "ref": "附件2"},
    {"key": "k2_share", "name": "K分摊2", "min": 0.7, "max": 1.0, "unit": "",
     "rule": "70% ~ 100%", "ref": "附件2"},
    {"key": "k3_share", "name": "K分摊3", "min": 0.0, "max": 1.0, "unit": "",
     "rule": "0% ~ 100%", "ref": "附件2"},
]

#: 缺省值（与 PricingEngine.calculate_jiangsu_2027 保持一致）
DEFAULTS = {
    "peak_coef": 1.6,
    "valley_coef": 0.4,
    "kp": 0.002,
    "service_fee": 2.0,
    "f_ratio": 0.05,
    "k1_share": 1.0,
    "k2_share": 1.0,
    "k3_share": 1.0,
    "green_mode": "否",
    "env_value": 30.0,
}


class ComplianceService:
    """2027 新规套餐参数合规校验。"""

    @staticmethod
    def rules() -> List[Dict[str, Any]]:
        return RULES

    @staticmethod
    def _params(config: Optional[dict]) -> Dict[str, Any]:
        cfg = dict(config or {})
        out = {}
        for k, default in DEFAULTS.items():
            v = cfg.get(k)
            out[k] = default if v is None else v
        # 兼容 kp / service_fee 两种写法（同额费用，仅单位不同：service_fee 元/MWh = kp 元/kWh × 1000）
        if cfg.get("service_fee") is None and cfg.get("kp") is not None:
            try:
                out["service_fee"] = float(cfg["kp"]) * 1000.0
            except (TypeError, ValueError):
                pass
        return out

    def validate(self, config: Optional[dict] = None) -> Dict[str, Any]:
        """返回 {valid, items, errors, warnings, params}。"""
        p = self._params(config)
        items: List[Dict[str, Any]] = []
        errors: List[str] = []
        warnings: List[str] = []

        for rule in RULES:
            key = rule["key"]
            raw = p.get(key)
            try:
                val = float(raw)
            except (TypeError, ValueError):
                items.append({**rule, "value": raw, "pass": False, "message": "取值非法"})
                errors.append("%s 取值非法（%r）" % (rule["name"], raw))
                continue

            ok = True
            if rule["min"] is not None and val < rule["min"]:
                ok = False
            if rule["max"] is not None and val > rule["max"]:
                ok = False

            items.append({**rule, "value": val, "pass": ok,
                          "message": "" if ok else "越界：%s（当前 %s）" % (rule["rule"], val)})
            if not ok:
                errors.append("%s 越界：要求 %s，当前 %s%s"
                              % (rule["name"], rule["rule"], val, rule["unit"]))

        # 绿电环境价值
        green_mode = p.get("green_mode") or "否"
        env_value = float(p.get("env_value") or 0)
        if green_mode in ("普通绿电", "小时级绿电") and env_value <= 0:
            warnings.append("已选择绿电但环境价值未设置（应 > 0 元/MWh）")

        if errors:
            warnings.append("存在越界项，按《江苏电力交易工作指引》第五条须经法定代表人确认后方可执行")

        return {
            "valid": not errors,
            "items": items,
            "errors": errors,
            "warnings": warnings,
            "params": p,
            "notice": "越界即触发风险预警，须法定代表人确认（交易工作指引第五条）",
        }
