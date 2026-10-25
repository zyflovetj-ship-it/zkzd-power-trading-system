import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { App as AntdApp, Button, Form, Input, Typography } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { login as loginApi } from '../api/auth';

function generateCaptcha(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789';
  let code = '';
  for (let i = 0; i < 5; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}

interface LoginFormValues {
  username: string;
  password: string;
  captcha: string;
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = AntdApp.useApp();
  const [loading, setLoading] = useState(false);
  const [captchaCode, setCaptchaCode] = useState(generateCaptcha);
  const [form] = Form.useForm<LoginFormValues>();
  const captchaCodeRef = useRef(captchaCode);
  captchaCodeRef.current = captchaCode;

  const refreshCaptcha = useCallback(() => {
    setCaptchaCode(generateCaptcha());
    form.setFieldValue('captcha', '');
  }, [form]);

  useEffect(() => {
    const saved = localStorage.getItem('rememberedUsername');
    if (saved) {
      form.setFieldValue('username', saved);
    }
  }, [form]);

  const onFinish = async (values: LoginFormValues) => {
    const inputCode = values.captcha?.toUpperCase() ?? '';
    if (inputCode !== captchaCodeRef.current) {
      message.error('验证码错误，请重新输入');
      refreshCaptcha();
      return;
    }

    setLoading(true);
    try {
      const token = await loginApi(values.username, values.password);
      localStorage.setItem('rememberedUsername', values.username);
      login(token);
      const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      message.error(detail ?? '用户名或密码错误');
      refreshCaptcha();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        width: '100%',
        height: '100vh',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      }}
    >
      {/* Left brand panel */}
      <div
        style={{
          flex: 1,
          background: 'linear-gradient(135deg, #0B2B5E 0%, #0A1C3A 100%)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '32px 48px',
          color: '#fff',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'radial-gradient(circle at 20% 40%, rgba(0, 212, 255, 0.08) 0%, transparent 50%)',
            pointerEvents: 'none',
          }}
        />

        <div style={{ position: 'relative', zIndex: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 80 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
              }}
            >
              <img src="/logo.svg" alt="Logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </div>
            <Typography style={{ fontSize: 24, fontWeight: 600, letterSpacing: 1, color: '#fff' }}>
              中科<span style={{ color: '#00D4FF', fontWeight: 700 }}>智电</span>
            </Typography>
          </div>

          <div style={{ marginBottom: 48 }}>
            <div style={{ fontSize: 36, fontWeight: 700, lineHeight: 1.2, marginBottom: 24, letterSpacing: -0.5, color: '#fff' }}>
              智慧能源<br />让交易更简单
            </div>
            <div
              style={{
                width: 80,
                height: 4,
                background: 'linear-gradient(90deg, #00D4FF, #0088FF)',
                borderRadius: 2,
                marginBottom: 24,
              }}
            />
            <div style={{ fontSize: 18, lineHeight: 1.5, color: 'rgba(255,255,255,0.75)', maxWidth: '85%' }}>
              AI预测 + 实时交易决策，为售电公司提供全栈数字化服务。
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginTop: 40 }}>
            {[
              '日前电价预测准确率 ≥ 95%',
              '支持多区域电力市场交易',
              '虚拟电厂 & 分布式资源聚合',
              '绿电溯源 & 碳资产管理',
            ].map((text, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 16, color: 'rgba(255,255,255,0.85)' }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    background: 'rgba(0, 212, 255, 0.15)',
                    borderRadius: '50%',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 16,
                    color: '#00D4FF',
                  }}
                >
                  ✓
                </div>
                {text}
              </div>
            ))}
          </div>
        </div>

        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', position: 'relative', zIndex: 2 }}>
          © 2026 zkzd电力交易系统
        </div>
      </div>

      {/* Right login panel */}
      <div
        style={{
          width: 520,
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px 40px',
          boxShadow: '-8px 0 30px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ width: '100%', maxWidth: 400 }}>
          <div style={{ marginBottom: 32 }}>
            <div style={{ fontSize: 28, fontWeight: 600, color: '#1E293B', marginBottom: 8 }}>
              欢迎回来
            </div>
            <div style={{ color: '#64748B', fontSize: 15 }}>
              请登录您的账户查看交易数据
            </div>
          </div>

          <Form
            form={form}
            name="login"
            onFinish={onFinish}
            size="large"
            layout="vertical"
            requiredMark={false}
          >
            <Form.Item
              label={<span style={{ fontSize: 14, fontWeight: 500, color: '#334155' }}>账号 / 手机号</span>}
              name="username"
              rules={[{ required: true, message: '请输入账号' }]}
            >
              <Input
                prefix={<UserOutlined style={{ color: '#94A3B8' }} />}
                placeholder="请输入注册手机号或邮箱"
                autoComplete="username"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>

            <Form.Item
              label={<span style={{ fontSize: 14, fontWeight: 500, color: '#334155' }}>密码</span>}
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: '#94A3B8' }} />}
                placeholder="请输入密码"
                autoComplete="current-password"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>

            <Form.Item
              label={<span style={{ fontSize: 14, fontWeight: 500, color: '#334155' }}>验证码</span>}
              name="captcha"
              rules={[{ required: true, message: '请输入验证码' }]}
            >
              <div style={{ display: 'flex', gap: 8 }}>
                <Input
                  placeholder="请输入验证码"
                  maxLength={6}
                  style={{ borderRadius: 8, flex: 1 }}
                />
                <div
                  onClick={refreshCaptcha}
                  style={{
                    width: 120,
                    height: 40,
                    background: '#F1F5F9',
                    borderRadius: 8,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: 'monospace',
                    fontSize: 20,
                    fontWeight: 'bold',
                    letterSpacing: 4,
                    color: '#1E293B',
                    cursor: 'pointer',
                    userSelect: 'none',
                    border: '1px solid #E2E8F0',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#E2E8F0'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = '#F1F5F9'; }}
                >
                  {captchaCode}
                </div>
              </div>
            </Form.Item>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, fontSize: 14 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#475569', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  defaultChecked
                  style={{ width: 16, height: 16, cursor: 'pointer', accentColor: '#1E88E5' }}
                  onChange={(e) => {
                    if (!e.target.checked) {
                      localStorage.removeItem('rememberedUsername');
                    }
                  }}
                />
                记住账号
              </label>
              <a href="#" style={{ color: '#1E88E5', textDecoration: 'none', fontWeight: 500 }}>
                忘记密码？
              </a>
            </div>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                block
                loading={loading}
                style={{
                  height: 48,
                  borderRadius: 8,
                  fontSize: 16,
                  fontWeight: 600,
                  border: 'none',
                  background: 'linear-gradient(105deg, #1E88E5 0%, #00ACC1 100%)',
                  boxShadow: '0 4px 10px rgba(0,136,229,0.2)',
                }}
              >
                登 录
              </Button>
            </Form.Item>

            <div style={{ textAlign: 'center', marginTop: 24, fontSize: 14, color: '#64748B' }}>
              还没有账号？
              <a href="#" style={{ color: '#1E88E5', textDecoration: 'none', fontWeight: 600, marginLeft: 4 }}>
                立即注册
              </a>
            </div>
          </Form>
        </div>
      </div>
    </div>
  );
}
