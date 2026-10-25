import { Navigate, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ProtectedRoute } from './router/ProtectedRoute';
import { AppLayout } from './layouts/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { Placeholder } from './components/Placeholder';
import { flatRoutes } from './router/menuConfig';
import CustomerPage from './pages/CustomerPage';
import ContractPage from './pages/ContractPage';
import PackagePage from './pages/PackagePage';
import SgccPricePage from './pages/SgccPricePage';
import TouRulePage from './pages/TouRulePage';
import RpaMonitorPage from './pages/RpaMonitorPage';
import CustomerLoadPage from './pages/CustomerLoadPage';
import LoadForecastOverallPage from './pages/LoadForecastOverallPage';
import LoadForecastShortTermPage from './pages/LoadForecastShortTermPage';
import LoadForecastAccuracyPage from './pages/LoadForecastAccuracyPage';
import LoadForecastLongTermPage from './pages/LoadForecastLongTermPage';
import SpotMarketPage from './pages/SpotMarketPage';
import SpotTrendPage from './pages/SpotTrendPage';
import MidLongPricePage from './pages/MidLongPricePage';
import MidLongTrendPage from './pages/MidLongTrendPage';
import PriceForecastBaselinePage from './pages/PriceForecastBaselinePage';
import PriceForecastD2Page from './pages/PriceForecastD2Page';
import PriceForecastDayAheadPage from './pages/PriceForecastDayAheadPage';
import PriceForecastMonthlyPage from './pages/PriceForecastMonthlyPage';
import ContractCurvePage from './pages/ContractCurvePage';
import MonthlyStrategyPage from './pages/MonthlyStrategyPage';
import D2StrategyPage from './pages/D2StrategyPage';
import DayAheadStrategyPage from './pages/DayAheadStrategyPage';
import CustomerClusterPage from './pages/CustomerClusterPage';
import RiskPositionContractsPage from './pages/RiskPositionContractsPage';
import RiskExposurePage from './pages/RiskExposurePage';
import RiskDashboardPage from './pages/RiskDashboardPage';
import SpotReviewPage from './pages/SpotReviewPage';
import SchedulerPage from './pages/SchedulerPage';
import SettlementWholesalePage from './pages/SettlementWholesalePage';
import SettlementBillReviewPage from './pages/SettlementBillReviewPage';
import SettlementRetailPage from './pages/SettlementRetailPage';
import SettlementProfitPage from './pages/SettlementProfitPage';
import LoadValidationPage from './pages/LoadValidationPage';
import UserPermissionsPage from './pages/UserPermissionsPage';
import ModelParametersPage from './pages/ModelParametersPage';
import DataTransferPage from './pages/DataTransferPage';

// 已落地的真实页面（随重写推进逐步扩充）
const pageMap: Record<string, ReactNode> = {
  '/customer/profiles': <CustomerPage />,
  '/customer/retail-contracts': <ContractPage />,
  '/basic-data/retail-packages': <PackagePage />,
  '/basic-data/grid-price': <SgccPricePage />,
  '/basic-data/tou-definition': <TouRulePage />,
  '/system-settings/data-access': <RpaMonitorPage />,
  '/customer/load-analysis': <CustomerLoadPage />,
  '/load-forecast/overall-analysis': <LoadForecastOverallPage />,
  '/load-forecast/short-term': <LoadForecastShortTermPage />,
  '/load-forecast/accuracy-analysis': <LoadForecastAccuracyPage />,
  '/load-forecast/long-term': <LoadForecastLongTermPage />,
  '/price-analysis/spot-market': <SpotMarketPage />,
  '/price-analysis/spot-trend': <SpotTrendPage />,
  '/price-analysis/mid-long-term': <MidLongPricePage />,
  '/price-analysis/mid-long-trend': <MidLongTrendPage />,
  '/price-forecast/baseline-data': <PriceForecastBaselinePage />,
  '/price-forecast/d-2': <PriceForecastD2Page />,
  '/price-forecast/day-ahead': <PriceForecastDayAheadPage />,
  '/price-forecast/monthly': <PriceForecastMonthlyPage />,
  '/trading-strategy/contract-curve': <ContractCurvePage />,
  '/trading-strategy/monthly': <MonthlyStrategyPage />,
  '/trading-strategy/d-2': <D2StrategyPage />,
  '/trading-strategy/day-ahead': <DayAheadStrategyPage />,
  '/customer/cluster-analysis': <CustomerClusterPage />,
  '/risk-management/position-contracts': <RiskPositionContractsPage />,
  '/risk-management/dashboard': <RiskDashboardPage />,
  '/risk-management/spot-review': <SpotReviewPage />,
  '/system-settings/scheduler': <SchedulerPage />,
  '/risk-management/exposure': <RiskExposurePage />,
  '/settlement/wholesale-pre-settlement': <SettlementWholesalePage />,
  '/settlement/bill-review': <SettlementBillReviewPage />,
  '/settlement/retail-settlement': <SettlementRetailPage />,
  '/settlement/profit-analysis': <SettlementProfitPage />,
  '/basic-data/load-validation': <LoadValidationPage />,
  '/system-settings/user-permissions': <UserPermissionsPage />,
  '/system-settings/data-transfer': <DataTransferPage />,
  '/system-settings/model-parameters': <ModelParametersPage />,
};

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />

          {/* 已落地页面直接挂载，其余菜单页先以占位页呈现 */}
          {flatRoutes
            .filter((r) => r.path !== '/dashboard')
            .map((r) => (
              <Route
                key={r.path}
                path={r.path}
                element={pageMap[r.path] ?? <Placeholder title={r.title} />}
              />
            ))}

          <Route path="*" element={<Placeholder title="页面不存在" />} />
        </Route>
      </Route>
    </Routes>
  );
}
