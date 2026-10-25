from pydantic import BaseModel, Field
from typing import List, Optional


class ClusterConfig(BaseModel):
    n_clusters: int = Field(3, ge=2, le=10, description="聚类数")
    features: List[str] = Field(default=["peak_valley_ratio", "load_rate", "volatility"], description="特征列表")


class ClusterResultItem(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    cluster: int = Field(0, description="簇编号")
    features: dict = Field(default_factory=dict, description="特征值")


class ClusterSummary(BaseModel):
    cluster_id: int = Field(..., description="簇编号")
    count: int = Field(0, description="客户数")
    avg_peak_valley_ratio: float = Field(0.0, description="平均峰谷比")
    avg_load_rate: float = Field(0.0, description="平均负荷率")
    avg_volatility: float = Field(0.0, description="平均波动性")


class ClusterData(BaseModel):
    config: ClusterConfig = Field(default_factory=ClusterConfig)
    results: List[ClusterResultItem] = Field(default_factory=list)
    summary: List[ClusterSummary] = Field(default_factory=list)
