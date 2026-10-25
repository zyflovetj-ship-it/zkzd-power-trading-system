from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class DashboardKPI(BaseModel):
    customer_count: int = Field(0, description="客户总数")
    active_customer_count: int = Field(0, description="执行中客户数")
    contract_count: int = Field(0, description="合同总数")
    active_contract_count: int = Field(0, description="生效中合同数")
    today_electricity: float = Field(0.0, description="今日电量(kWh)")
    total_cost: float = Field(0.0, description="累计成本(元)")
    saving_rate: float = Field(0.0, description="节省率(%)")


class DailyElectricityItem(BaseModel):
    date: str = Field(..., description="日期")
    value: float = Field(..., description="电量(kWh)")


class ContractStatusItem(BaseModel):
    status: str = Field(..., description="状态")
    count: int = Field(..., description="数量")


class RecentActivityItem(BaseModel):
    id: str = Field(..., description="记录ID")
    type: str = Field(..., description="类型")
    description: str = Field(..., description="描述")
    timestamp: datetime = Field(..., description="时间")


class DashboardData(BaseModel):
    kpi: DashboardKPI = Field(default_factory=DashboardKPI, description="核心指标")
    daily_electricity: List[DailyElectricityItem] = Field(default_factory=list, description="近30天电量趋势")
    contract_status: List[ContractStatusItem] = Field(default_factory=list, description="合同状态分布")
    recent_activities: List[RecentActivityItem] = Field(default_factory=list, description="最近动态")