import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
    // 每次 API 请求都刷新最后活动时间（AuthContext 的 inactivity timer 会读取此值）
    localStorage.setItem('lastActivity', String(Date.now()));
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('lastActivity');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

/**
 * 以带鉴权（Bearer token）的方式下载文件并触发浏览器保存。
 * 关键：必须用 axios 请求（经拦截器注入 Authorization），不能 window.location 裸跳转，
 * 否则浏览器导航不带 token，后端 401 Not authenticated。
 */
export async function downloadAuthFile(url: string, filename: string): Promise<void> {
  const res = await apiClient.get(url, { responseType: 'blob' });
  const blob = new Blob([res.data]);
  const disposition = res.headers['content-disposition'];
  let name = filename;
  if (disposition) {
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (match) name = match[1].replace(/['"]/g, '');
  }
  const objUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objUrl;
  a.download = name;
  a.click();
  setTimeout(() => window.URL.revokeObjectURL(objUrl), 1000);
}

export default apiClient;
