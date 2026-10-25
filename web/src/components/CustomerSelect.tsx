import { Select } from 'antd';
import type { CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCustomers } from '@/api/customers';

interface CustomerSelectProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  style?: CSSProperties;
  allowClear?: boolean;
}

// 交易/分析页共用的客户选择器：加载在执行的客户，支持搜索。
export function CustomerSelect({ value, onChange, placeholder = '选择客户', style, allowClear = true }: CustomerSelectProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['activeCustomersForSelect'],
    queryFn: () => fetchCustomers({ status: 'active', page_size: 200 }),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Select
      showSearch
      allowClear={allowClear}
      value={value || undefined}
      placeholder={placeholder}
      style={style ?? { width: 240 }}
      loading={isLoading}
      onChange={(v) => onChange?.(v ?? '')}
      optionFilterProp="label"
      options={(data?.items ?? []).map((c) => ({
        value: c.id,
        label: c.short_name || c.user_name,
      }))}
    />
  );
}
