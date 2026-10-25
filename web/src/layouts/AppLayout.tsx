import { useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
import { Dropdown, Space } from 'antd';
import { UserOutlined, LogoutOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { proLayoutRoute } from '../router/menuConfig';
import { useAuth } from '../contexts/AuthContext';

const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];

function Clock() {
  const [now, setNow] = useState(dayjs());
  useEffect(() => {
    const id = setInterval(() => setNow(dayjs()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span style={{ color: 'rgba(0,0,0,0.45)', fontSize: 13, whiteSpace: 'nowrap', marginRight: 20 }}>
      {now.format('YYYY-MM-DD')} {weekdays[now.day()]} {now.format('HH:mm')}
    </span>
  );
}

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { username, logout } = useAuth();

  return (
    <>
      <style>{'.ant-pro-sider-logo h1 { white-space: nowrap; }'}</style>
      <ProLayout
      title="zkzd电力交易系统"
      logo={<img src="/logo.svg" alt="Logo" style={{ height: 28, width: 28 }} />}
      route={proLayoutRoute}
      location={{ pathname: location.pathname }}
      menuProps={{
        onClick: ({ key }) => {
          if (key && key !== location.pathname) navigate(key);
        },
      }}
      layout="side"
      fixSiderbar
      siderWidth={220}
      rightContentRender={() => (
        <>
          <Clock />
          <Dropdown
            menu={{
              items: [
                {
                  key: 'userinfo',
                  label: (
                    <div style={{ padding: '4px 0' }}>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{username ?? '用户'}</div>
                      <div style={{ color: '#999', fontSize: 12, marginTop: 2 }}>管理员</div>
                    </div>
                  ),
                  disabled: true,
                },
                { type: 'divider' },
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出系统',
                  onClick: logout,
                },
              ],
            }}
          >
            <Space style={{ cursor: 'pointer' }}>
              <UserOutlined />
              <span>{username ?? '用户'}</span>
            </Space>
          </Dropdown>
        </>
      )}
      token={{
        header: { colorBgHeader: '#ffffff' },
      }}
    >
      <Outlet />
    </ProLayout>
    </>
  );
}
