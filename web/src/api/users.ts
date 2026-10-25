import apiClient from './client';

export type Role = '管理员' | '交易员' | '风控' | '只读';

export interface UserRecord {
  id: string;
  username: string;
  full_name?: string;
  email?: string;
  department?: string;
  role: Role;
  is_active: boolean;
  last_login?: string;
  created_at?: string;
}

export interface UserListResponse {
  total: number;
  items: UserRecord[];
}

export interface CreateUserData {
  username: string;
  full_name?: string;
  email?: string;
  department?: string;
  role: Role;
  password: string;
}

export interface UpdateUserData {
  full_name?: string;
  email?: string;
  department?: string;
  role?: Role;
  is_active?: boolean;
}

export const getSystemUsers = (params?: { keyword?: string; page?: number; page_size?: number }) =>
  apiClient.get<UserListResponse>('/api/v1/system/users/', { params }).then((r) => r.data);

export const createUser = (data: CreateUserData) =>
  apiClient.post<UserRecord>('/api/v1/system/users/', data).then((r) => r.data);

export const updateUser = (userId: string, data: UpdateUserData) =>
  apiClient.put<UserRecord>(`/api/v1/system/users/${userId}`, data).then((r) => r.data);

export const deleteUser = (userId: string) =>
  apiClient.delete(`/api/v1/system/users/${userId}`);

export const resetPassword = (userId: string, password: string) =>
  apiClient.post(`/api/v1/system/users/${userId}/reset-password`, { password });
