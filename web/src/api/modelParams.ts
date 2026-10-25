import apiClient from './client';

// 预测模型参数模块

export type ModelType = '负荷预测' | '价格预测';
export type EnableStatus = 'enabled' | 'disabled';

export interface ModelRecord {
  name: string;
  type: ModelType;
  version: string;
  params: string;
  status: EnableStatus;
  updatedAt: string;
  mae: number;
}

export interface ModelParamsResp {
  models: ModelRecord[];
}

export const getModelParameters = () =>
  apiClient.get<ModelParamsResp>('/api/v1/system/model-parameters/').then((r) => r.data);
