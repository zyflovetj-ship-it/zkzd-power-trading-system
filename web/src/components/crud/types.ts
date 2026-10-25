// CrudPage 通用配置类型

export type CrudFieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'month' // 年月 YYYY-MM，表单内用 dayjs，提交时由 fromFormValues 转字符串
  | 'switch';

export interface CrudField {
  name: string;
  label: string;
  type: CrudFieldType;
  required?: boolean;
  options?: { label: string; value: string | number | boolean }[];
  placeholder?: string;
  /** 栅格占位（0-24），默认 24（整行） */
  span?: number;
  /** 编辑时禁用该字段 */
  disabledOnEdit?: boolean;
  /** 级联依赖：此字段的选项依赖于另一个字段的值 */
  dependsOn?: string;
  /** 根据依赖字段值动态加载选项（dependsOn 不为空时生效） */
  fetchOptions?: (depsValue: any, form: any) => Promise<{ label: string; value: string }[]>;
}

export interface SearchField {
  name: string;
  label: string;
  type: 'text' | 'select';
  options?: { label: string; value: string }[];
  placeholder?: string;
}

export interface CrudPageProps<T extends Record<string, any>> {
  title: string;
  rowKey?: string;
  columns: import('antd/es/table').ColumnsType<T>;
  searchFields?: SearchField[];
  formFields: CrudField[];
  /** 分页/筛选查询，返回 items 与 total */
  fetcher: (params: {
    page: number;
    pageSize: number;
    filters: Record<string, any>;
  }) => Promise<{ items: T[]; total: number }>;
  creator?: (values: Partial<T>) => Promise<unknown>;
  updater?: (id: string, values: Partial<T>) => Promise<unknown>;
  remover?: (id: string) => Promise<unknown>;
  /** 整行操作列（完全自定义，覆盖默认的编辑/删除按钮） */
  actions?: (record: T) => React.ReactNode;
  /** 在默认编辑/删除按钮之外追加的操作节点 */
  rowActions?: (record: T) => React.ReactNode;
  /** 工具栏右侧额外按钮（如导入/导出） */
  toolbarExtra?: React.ReactNode;
  /** 编辑时把记录转为表单初始值 */
  toFormValues?: (record: T) => Record<string, any>;
  /** 提交时把表单值转为接口载荷 */
  fromFormValues?: (values: Record<string, any>) => Partial<T>;
  /** 禁用新增按钮 */
  disableCreate?: boolean;
  /** 暴露内部刷新函数，供自定义操作（如状态流转）在调用接口后触发列表重载 */
  reloadRef?: React.MutableRefObject<() => void>;
  /** 暴露内部"打开编辑弹窗"函数，供自定义操作列调用 */
  editRef?: React.MutableRefObject<(record: T) => void>;
  /** 在表单底部额外渲染自定义内容（如嵌套数组字段 Form.List） */
  renderExtraFormContent?: (editing: boolean) => React.ReactNode;
  /** 编辑前异步获取完整数据（返回的数据会作为表单初始值） */
  onBeforeEdit?: (record: T) => Promise<Record<string, any>>;
}
