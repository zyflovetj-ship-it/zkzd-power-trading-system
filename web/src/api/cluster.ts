import apiClient from './client';

// 客户聚类分析模块 - 真实后端 API

export interface ClusterFeature {
  peak_valley_ratio: number;
  load_rate: number;
  volatility: number;
}

export interface ClusterResultItem {
  customer_id: string;
  customer_name: string;
  cluster: number;
  features: ClusterFeature;
}

export interface ClusterSummaryItem {
  cluster_id: number;
  count: number;
  avg_peak_valley_ratio: number;
  avg_load_rate: number;
  avg_volatility: number;
}

export interface ClusterConfig {
  n_clusters: number;
  features: string[];
}

export interface CustomerClusterResp {
  config: ClusterConfig;
  results: ClusterResultItem[];
  summary: ClusterSummaryItem[];
}

export const runCustomerCluster = (nClusters: number = 3) =>
  apiClient.post<CustomerClusterResp>('/api/v1/customer-cluster', {
    n_clusters: nClusters,
    features: ['peak_valley_ratio', 'load_rate', 'volatility']
  }).then((r) => r.data);
