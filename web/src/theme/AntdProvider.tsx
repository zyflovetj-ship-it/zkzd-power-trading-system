import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import type { ReactNode } from 'react';
import { themeConfig } from './themeConfig';

dayjs.locale('zh-cn');

export function AntdProvider({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider theme={themeConfig} locale={zhCN}>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
