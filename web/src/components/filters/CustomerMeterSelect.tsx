import { useEffect, useState } from 'react';
import { Select, Space, Spin } from 'antd';
import { getUsers, getMeters } from '@/api/loadForecast';

interface Value {
  userName?: string;
  meterId?: string;
}

interface Props {
  value?: Value;
  onChange: (v: Value) => void;
  disabled?: boolean;
}

// 企业简称 → 户号 两级级联选择（客户负荷分析页专用）。
// 下拉框显示户号(account_id)，但实际查询用 meter_id。
export function CustomerMeterSelect({ value, onChange, disabled }: Props) {
  const [users, setUsers] = useState<{ value: string; label: string }[]>([]);
  const [meterOptions, setMeterOptions] = useState<{ value: string; label: string }[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingMeters, setLoadingMeters] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoadingUsers(true);
    getUsers()
      .then((list) => {
        if (!alive) return;
        setUsers(list.map((u) => ({ value: u.user_name, label: u.user_name })));
      })
      .catch(() => {})
      .finally(() => alive && setLoadingUsers(false));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!value?.userName) {
      setMeterOptions([]);
      return;
    }
    let alive = true;
    setLoadingMeters(true);
    getMeters(value.userName)
      .then((list) => {
        if (!alive) return;
        setMeterOptions(list.map((m) => ({ value: m.meter_id, label: m.account_id })));
      })
      .catch(() => {})
      .finally(() => alive && setLoadingMeters(false));
    return () => {
      alive = false;
    };
  }, [value?.userName]);

  return (
    <Space wrap>
      <Spin spinning={loadingUsers}>
        <Select
          placeholder="选择企业简称"
          style={{ width: 220 }}
          showSearch
          optionFilterProp="label"
          value={value?.userName}
          disabled={disabled}
          options={users}
          loading={loadingUsers}
          onChange={(userName) => onChange({ userName, meterId: undefined })}
          allowClear
        />
      </Spin>
      <Spin spinning={loadingMeters}>
        <Select
          placeholder="选择户号"
          style={{ width: 200 }}
          showSearch
          optionFilterProp="label"
          value={value?.meterId}
          disabled={disabled || !value?.userName}
          options={meterOptions}
          loading={loadingMeters}
          onChange={(meterId) => onChange({ userName: value?.userName, meterId })}
          allowClear
        />
      </Spin>
    </Space>
  );
}
