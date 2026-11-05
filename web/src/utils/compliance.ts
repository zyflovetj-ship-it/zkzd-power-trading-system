/** 2027 新规套餐参数校验（前端即时校验，与后端 compliance_service 规则一致）。 */

export interface ParamRule {
  key: string;
  name: string;
  min: number | null;
  max: number | null;
  unit: string;
  rule: string;
  ref: string;
}

export const PARAM_RULES: ParamRule[] = [
  { key: 'peak_coef', name: '① 峰段系数', min: 1.6, max: null, unit: '', rule: '≥1.6（上浮≥60%）', ref: '附件2 第1项' },
  { key: 'valley_coef', name: '① 谷段系数', min: null, max: 0.4, unit: '', rule: '≤0.4（下浮≥60%）', ref: '附件2 第1项' },
  { key: 'service_fee', name: '② 售电服务费（P浮动）', min: 2, max: 20, unit: '元/MWh', rule: '2 ~ 20 元/MWh', ref: '附件2 第2项' },
  { key: 'k1_share', name: '③ 成本补偿分摊系数 K分摊1', min: 1.0, max: 1.0, unit: '', rule: '参考值 100%', ref: '附件2' },
  { key: 'k2_share', name: '④ k1 不平衡费用返还系数', min: 0.7, max: 1.0, unit: '', rule: '70% ~ 100%', ref: '附件2' },
  { key: 'k3_share', name: '⑤ k2 市场调节费用返还系数', min: 0.0, max: 1.0, unit: '', rule: '0 ~ 100%', ref: '附件2' },
  { key: 'f_ratio', name: '⑥ F 电能量封顶浮动系数', min: 0.0, max: 0.05, unit: '', rule: '0 ~ 5%', ref: '附件2' },
];

export interface CheckItem {
  key: string;
  name: string;
  value: number;
  display: string;
  unit: string;
  pass: boolean;
  rule: string;
  ref: string;
  message: string;
}

export interface CheckResult {
  valid: boolean;
  items: CheckItem[];
  violations: CheckItem[];
}

const pct = (v: number) => (v * 100).toFixed(0) + '%';

export function checkParams(p: {
  peak_coef?: number;
  valley_coef?: number;
  service_fee?: number;
  k1_share?: number;
  k2_share?: number;
  k3_share?: number;
  f_ratio?: number;
}): CheckResult {
  const items: CheckItem[] = [];
  for (const r of PARAM_RULES) {
    const raw = p[r.key as keyof typeof p];
    const val = Number(raw ?? 0);
    let pass = true;
    if (r.min != null && val < r.min) pass = false;
    if (r.max != null && val > r.max) pass = false;
    const isRatio = r.key === 'k1_share' || r.key === 'k2_share' || r.key === 'k3_share' || r.key === 'f_ratio';
    const display = isRatio ? pct(val) : String(val);
    items.push({
      key: r.key,
      name: r.name,
      value: val,
      display,
      unit: r.unit,
      pass,
      rule: r.rule,
      ref: r.ref,
      message: pass ? '' : '越界：要求 ' + r.rule + '，当前 ' + display + r.unit,
    });
  }
  const violations = items.filter((i) => !i.pass);
  return { valid: violations.length === 0, items, violations };
}
