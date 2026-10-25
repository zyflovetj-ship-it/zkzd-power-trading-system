// 从运行中的后端生成前端 TS 类型。
// 前置：后端需在 8005 运行并暴露 /openapi.json（FastAPI 自动生成）。
// 也可将 openapi.json 下载到本地后改为从文件读取：
//   npx openapi-typescript ./openapi.json -o src/types/api.d.ts
import { execSync } from 'node:child_process';

const OPENAPI_URL = process.env.OPENAPI_URL || 'http://127.0.0.1:8005/openapi.json';
const OUTPUT = 'src/types/api.d.ts';

try {
  console.log(`[gen:api] 拉取 OpenAPI: ${OPENAPI_URL}`);
  execSync(`npx openapi-typescript ${OPENAPI_URL} -o ${OUTPUT}`, { stdio: 'inherit' });
  console.log(`[gen:api] 已生成 -> ${OUTPUT}`);
} catch (err) {
  console.error('[gen:api] 生成失败，请确认后端已启动且可访问 /openapi.json');
  process.exit(1);
}
