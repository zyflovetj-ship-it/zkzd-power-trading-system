import type { ReactNode } from 'react';
import {
  DashboardOutlined,
  TeamOutlined,
  LineChartOutlined,
  FundOutlined,
  AreaChartOutlined,
  SwapOutlined,
  AlertOutlined,
  AccountBookOutlined,
  DatabaseOutlined,
  SettingOutlined,
} from '@ant-design/icons';

// ProLayout 菜单路由树（同时驱动侧栏与面包屑）
export interface AppRoute {
  path: string;
  name?: string;
  icon?: ReactNode;
  routes?: AppRoute[];
}

export const proLayoutRoute: AppRoute = {
  path: '/',
  routes: [
    { path: '/dashboard', name: '交易总览', icon: <DashboardOutlined /> },
    {
      path: '/customer',
      name: '客户管理',
      icon: <TeamOutlined />,
      routes: [
        { path: '/customer/profiles', name: '客户档案管理' },
        { path: '/customer/retail-contracts', name: '零售合同管理' },
        { path: '/customer/load-analysis', name: '客户负荷分析' },
        { path: '/customer/cluster-analysis', name: '客户聚类分析' },
      ],
    },
    {
      path: '/load-forecast',
      name: '负荷预测',
      icon: <LineChartOutlined />,
      routes: [
        { path: '/load-forecast/overall-analysis', name: '总体负荷分析' },
        { path: '/load-forecast/short-term', name: '短期负荷预测' },
        { path: '/load-forecast/accuracy-analysis', name: '预测精度分析' },
        { path: '/load-forecast/long-term', name: '中长期负荷预测' },
      ],
    },
    {
      path: '/price-analysis',
      name: '价格分析',
      icon: <FundOutlined />,
      routes: [
        { path: '/price-analysis/spot-market', name: '现货价格分析' },
        { path: '/price-analysis/spot-trend', name: '现货趋势分析' },
        { path: '/price-analysis/mid-long-term', name: '中长期价格分析' },
        { path: '/price-analysis/mid-long-trend', name: '中长期趋势分析' },
      ],
    },
    {
      path: '/price-forecast',
      name: '价格预测',
      icon: <AreaChartOutlined />,
      routes: [
        { path: '/price-forecast/baseline-data', name: '预测基础数据' },
        { path: '/price-forecast/d-2', name: 'D-2价格预测' },
        { path: '/price-forecast/day-ahead', name: '日前价格预测' },
        { path: '/price-forecast/monthly', name: '月度价格预测' },
      ],
    },
    {
      path: '/trading-strategy',
      name: '交易决策',
      icon: <SwapOutlined />,
      routes: [
        { path: '/trading-strategy/contract-curve', name: '合同曲线生成' },
        { path: '/trading-strategy/monthly', name: '月度交易策略' },
        { path: '/trading-strategy/d-2', name: 'D-2交易策略' },
        { path: '/trading-strategy/day-ahead', name: '日前交易策略' },
      ],
    },
    {
      path: '/risk-management',
      name: '风险管理',
      icon: <AlertOutlined />,
      routes: [
        { path: '/risk-management/dashboard', name: '风险驾驶舱' },
        { path: '/risk-management/position-contracts', name: '持仓合约管理' },
        { path: '/risk-management/exposure', name: '风险敞口分析' },
        { path: '/risk-management/spot-review', name: '现货交易复盘' },
      ],
    },
    {
      path: '/settlement',
      name: '结算管理',
      icon: <AccountBookOutlined />,
      routes: [
        { path: '/settlement/wholesale-pre-settlement', name: '批发侧预结算' },
        { path: '/settlement/bill-review', name: '平台账单复核' },
        { path: '/settlement/retail-settlement', name: '零售用户结算' },
        { path: '/settlement/profit-analysis', name: '经营利润分析' },
      ],
    },
    {
      path: '/basic-data',
      name: '基础数据',
      icon: <DatabaseOutlined />,
      routes: [
        { path: '/basic-data/grid-price', name: '国网代购电价格' },
        { path: '/basic-data/tou-definition', name: '分时电价划分' },
        { path: '/basic-data/retail-packages', name: '零售套餐管理' },
        { path: '/basic-data/load-validation', name: '负荷数据校验' },
      ],
    },
    {
      path: '/system-settings',
      name: '系统管理',
      icon: <SettingOutlined />,
      routes: [
        { path: '/system-settings/user-permissions', name: '用户与权限' },
        { path: '/system-settings/data-transfer', name: '数据导入导出' },
        { path: '/system-settings/data-access', name: '数据接入管理' },
        { path: '/system-settings/model-parameters', name: '预测模型参数' },
        { path: '/system-settings/scheduler', name: '定时任务监控' },
      ],
    },
  ],
};

// 拍平为叶子路由（用于 react-router 注册与面包屑标题查找）
export interface FlatRoute {
  path: string;
  title: string;
  parent?: string;
}

function flatten(list: AppRoute[], parent?: string): FlatRoute[] {
  const result: FlatRoute[] = [];
  for (const r of list) {
    if (r.routes && r.routes.length > 0) {
      result.push(...flatten(r.routes, r.name));
    } else {
      result.push({ path: r.path, title: r.name ?? r.path, parent });
    }
  }
  return result;
}

export const flatRoutes: FlatRoute[] = flatten(proLayoutRoute.routes ?? []);

export function findRouteTitle(path: string): string {
  return flatRoutes.find((r) => r.path === path)?.title ?? '未命名页面';
}
