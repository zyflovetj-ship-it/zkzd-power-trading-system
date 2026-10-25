import type { ThemeConfig } from 'antd';

// zkzd电力交易系统 主题令牌
// 品牌色采用沉稳“电力蓝”，浅灰布局底突出内容卡片。
export const themeConfig: ThemeConfig = {
  token: {
    colorPrimary: '#0958d9',
    borderRadius: 6,
    colorBgLayout: '#f5f7fa',
    fontSize: 14,
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ff4d4f',
    colorInfo: '#0958d9',
  },
  components: {
    Layout: {
      headerBg: '#ffffff',
      siderBg: '#001529',
      headerHeight: 56,
    },
    Menu: {
      itemSelectedBg: '#e6f4ff',
      itemSelectedColor: '#0958d9',
      darkItemBg: '#001529',
      darkItemSelectedBg: '#0958d9',
    },
    Table: {
      headerBg: '#fafafa',
      headerColor: 'rgba(0,0,0,0.88)',
    },
    Card: {
      borderRadiusLG: 8,
    },
  },
};
