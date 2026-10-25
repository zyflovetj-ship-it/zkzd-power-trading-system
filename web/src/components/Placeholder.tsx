import { Empty, Typography } from 'antd';
import { ToolOutlined } from '@ant-design/icons';

// 临时占位页：逐页替换后删除。
export function Placeholder({ title }: { title: string }) {
  return (
    <div style={{ padding: 48, textAlign: 'center' }}>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <Typography.Text type="secondary">
            「{title}」页面建设中
          </Typography.Text>
        }
      />
      <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
        <ToolOutlined /> 该模块将在后续阶段（P2–P4）以 Ant Design 重写并接入真实后端接口。
      </Typography.Paragraph>
    </div>
  );
}
