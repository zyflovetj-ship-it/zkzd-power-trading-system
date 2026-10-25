import apiClient from './client';

// 登录：OAuth2 密码模式，form-encoded POST /api/v1/token
export async function login(
  username: string,
  password: string,
): Promise<string> {
  const body = new URLSearchParams();
  body.set('username', username);
  body.set('password', password);

  const { data } = await apiClient.post('/api/v1/token', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data.access_token as string;
}
