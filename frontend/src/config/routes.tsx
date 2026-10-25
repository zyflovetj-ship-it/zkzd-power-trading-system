import React from 'react';
import { LoadAnalysisPage } from '../pages/LoadAnalysisPage';
import { MarketPriceAnalysisPage } from '../pages/MarketPriceAnalysisPage';
import PlaceholderPage from '../components/PlaceholderPage';
import GridAgencyPricePage from '../pages/GridAgencyPricePage';
import RetailPackagePage from '../pages/RetailPackagePage';
import { CustomerManagementPage } from '../pages/CustomerManagementPage';
import RetailContractPage from '../pages/RetailContractPage';
import { ForecastBaseDataPage } from '../pages/ForecastBaseDataPage';
import { SpotTrendAnalysisPage } from '../pages/SpotTrendAnalysisPage';
import TouRulesPage from '../pages/TouRulesPage';
import { ContractPriceDailyPage } from '../pages/ContractPriceDailyPage';
import { ContractPriceTrendPage } from '../pages/ContractPriceTrendPage';
import { RpaMonitorPage } from '../pages/RpaMonitorPage';
import { ShortTermLoadForecastPage } from '../pages/ShortTermLoadForecastPage';
import { MediumLongTermForecastPage } from '../pages/MediumLongTermForecastPage';
import {D2PriceForecastPage} from '../pages/D2PriceForecastPage'
import {DayAheadPriceForecastPage} from '../pages/DayAheadPriceForecastPage'
import {MonthlyPriceForecastPage} from '../pages/MonthlyPriceForecastPage'
import {ContractCurveGenerationPage} from '../pages/ContractCurveGenerationPage'
import {D2TradingStrategyPage} from '../pages/D2TradingStrategyPage'
import {MonthlyTradingStrategyPage} from '../pages/MonthlyTradingStrategyPage'
import {DayAheadTradingStrategyPage} from '../pages/DayAheadTradingStrategyPage'
import {MediumLongTermReviewPage} from '../pages/MediumLongTermReviewPage'
import {CustomerClusterPage} from '../pages/CustomerClusterPage'
// 路由配置接口
export interface RouteConfig {
    path: string;
    title: string;
    component: React.ComponentType;
}

// 路由配置列表
export const routeConfigs: RouteConfig[] = [
    { path: '/dashboard', title: '交易总览', component: PlaceholderPage },

    // 客户管理
    { path: '/customer/profiles', title: '客户档案管理', component: CustomerManagementPage },
    { path: '/customer/retail-contracts', title: '零售合同管理', component: RetailContractPage },
    { path: '/customer/load-analysis', title: '客户负荷分析', component: LoadAnalysisPage },
    { path: '/customer/cluster-analysis', title: '客户聚类分析', component: CustomerClusterPage },

    // 负荷预测
    { path: '/load-forecast/overall-analysis', title: '总体负荷分析', component: LoadAnalysisPage },
    { path: '/load-forecast/short-term', title: '短期负荷预测', component: ShortTermLoadForecastPage },
    { path: '/load-forecast/accuracy-analysis', title: '预测精度分析', component: PlaceholderPage },
    { path: '/load-forecast/long-term', title: '中长期负荷预测', component: MediumLongTermForecastPage },

    // 价格分析
    { path: '/price-analysis/spot-market', title: '现货日内分析', component: MarketPriceAnalysisPage },
    { path: '/price-analysis/spot-trend', title: '现货趋势分析', component: SpotTrendAnalysisPage },
    { path: '/price-analysis/mid-long-term', title: '中长期日内分析', component: ContractPriceDailyPage },
    { path: '/price-analysis/mid-long-trend', title: '中长期趋势分析', component: ContractPriceTrendPage },


    // 价格预测
    { path: '/price-forecast/baseline-data', title: '预测基础数据', component: ForecastBaseDataPage },
    { path: '/price-forecast/d-2', title: 'D-2价格预测', component: D2PriceForecastPage },
    { path: '/price-forecast/day-ahead', title: '日前价格预测', component: DayAheadPriceForecastPage },
    { path: '/price-forecast/monthly', title: '月度价格预测', component: MonthlyPriceForecastPage },

    // 交易决策
    { path: '/trading-strategy/contract-curve', title: '合同曲线生成', component: ContractCurveGenerationPage },
    { path: '/trading-strategy/monthly', title: '月度交易策略', component: MonthlyTradingStrategyPage },
    { path: '/trading-strategy/d-2', title: 'D-2交易策略', component: D2TradingStrategyPage },
    { path: '/trading-strategy/day-ahead', title: '日前交易策略', component: DayAheadTradingStrategyPage },

    // 风险管理
    { path: '/risk-management/position-contracts', title: '持仓合约管理', component: MediumLongTermReviewPage },
    { path: '/risk-management/exposure', title: '风险敞口分析', component: PlaceholderPage },

    // 结算管理
    { path: '/settlement/wholesale-pre-settlement', title: '批发侧预结算', component: PlaceholderPage },
    { path: '/settlement/bill-review', title: '平台账单复核', component: PlaceholderPage },
    { path: '/settlement/retail-settlement', title: '零售用户结算', component: PlaceholderPage },
    { path: '/settlement/profit-analysis', title: '经营利润分析', component: PlaceholderPage },

    // 基础数据
    { path: '/basic-data/grid-price', title: '国网代理购电', component: GridAgencyPricePage },
    { path: '/basic-data/tou-definition', title: '时段电价分布', component: TouRulesPage },
    { path: '/basic-data/retail-packages', title: '零售套餐管理', component: RetailPackagePage },
    { path: '/basic-data/load-validation', title: '负荷数据校验', component: PlaceholderPage },

    // 系统管理
    { path: '/system-settings/user-permissions', title: '用户与权限', component: PlaceholderPage },
    { path: '/system-settings/data-access', title: '数据下载监控', component: RpaMonitorPage },
    { path: '/system-settings/model-parameters', title: '预测模型参数', component: PlaceholderPage },
];

// 根据路径获取路由配置
export const getRouteConfig = (path: string): RouteConfig | undefined => {
    return routeConfigs.find(config => config.path === path);
};
