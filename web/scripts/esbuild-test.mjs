import * as esbuild from 'esbuild';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const outDir = path.join(root, '.esbuild-test');
fs.mkdirSync(outDir, { recursive: true });

const result = await esbuild.build({
  entryPoints: [path.join(root, 'src/main.tsx')],
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2020',
  jsx: 'automatic',
  outfile: path.join(outDir, 'bundle.js'),
  // 处理 @/ 别名（esbuild 原生 alias 对 scope 前缀不可靠，用插件兜底）
  plugins: [
    {
      name: 'alias-at',
      setup(build) {
        build.onResolve({ filter: /^@\// }, (args) => {
          const abs = path.join(root, 'src', args.path.slice(2));
          const exts = ['.ts', '.tsx', '.js', '.jsx', '.json'];
          for (const e of exts) {
            if (fs.existsSync(abs + e)) return { path: abs + e };
          }
          if (fs.existsSync(path.join(abs, 'index.ts')))
            return { path: path.join(abs, 'index.ts') };
          if (fs.existsSync(path.join(abs, 'index.tsx')))
            return { path: path.join(abs, 'index.tsx') };
          return { path: abs };
        });
      },
    },
  ],
  define: {
    'import.meta.env.VITE_API_BASE_URL': '""',
  },
  loader: { '.css': 'css' },
  logLevel: 'info',
  metafile: true,
});

const bytes = fs.statSync(path.join(outDir, 'bundle.js')).size;
console.log(`\n✅ ESBUILD BUNDLE OK — ${bytes} bytes`);
// 统计被打包的模块数（粗略）
const inputs = Object.keys(result.metafile.inputs).length;
console.log(`📦 打包模块数: ${inputs}`);
