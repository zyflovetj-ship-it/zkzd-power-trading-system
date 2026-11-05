import { useEffect } from 'react';
import { App } from 'antd';
import type { CheckResult } from '@/utils/compliance';

interface Props {
  result: CheckResult;
  compact?: boolean;
}

/**
 * 合规校验提示组件。
 * 设计：越界不再用内联红色 Alert 块（会撑开卡片、打乱布局），
 * 改为右上角 notification 弹窗提示，且不重复刷屏（根据越界 key 去重）。
 * 注意：必须用 App.useApp() 提供的 notification 实例（项目全局被 <App> 包裹，
 * 静态 notification 拿不到 context 不会渲染）。
 * 真正的「法人二次确认」仍由测算按钮的 modal.confirm 处理。
 */
export function ComplianceBanner({ result, compact }: Props) {
  const { notification } = App.useApp();
  const violationsKey = result.violations.map((v) => v.key + ':' + v.display).join('|');

  useEffect(() => {
    if (result.valid || !violationsKey) return;
    const key = 'compliance-' + violationsKey;
    notification.warning({
      key,
      message: '参数越界 —— 触发风险预警',
      description: (
        <div>
          <div style={{ marginBottom: 6 }}>
            以下 {result.violations.length} 项超出附件2 合规区间，须经法定代表人确认后方可执行：
          </div>
          {result.violations.map((v) => (
            <div key={v.key} style={{ marginBottom: 2 }}>
              • {v.name}：要求 {v.rule}，当前 {v.display}{v.unit}
            </div>
          ))}
        </div>
      ),
      duration: 4.5,
      placement: 'topRight',
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [violationsKey, result.valid, notification]);

  // 合规时返回空，不占用页面布局
  return null;
}
