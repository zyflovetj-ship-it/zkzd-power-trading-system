# 前端镜像：多阶段构建（Node 构建 -> nginx 托管）
# 构建上下文为仓库根目录（docker-compose 指定 context: .），故路径以 web/ 开头。
FROM node:20-slim AS build

WORKDIR /app

# 拷贝 package.json + package-lock.json，利用 Docker 层缓存
# 用 npm ci 严格按 lock 安装：npm install 按 ^ 范围解析最新版，
# 曾因 TypeScript 版本漂移导致「本地能过、容器报错」的不可重现构建。
COPY web/package.json web/package-lock.json ./
RUN npm ci

# 拷贝源码并构建
COPY web/ ./
# 生产 API 基址必须留空：前端调用路径本身含 /api/v1/...，
# 由下方 nginx 的 /api 反代转发到后端，避免 /api/api/v1 双前缀。
ENV VITE_API_BASE_URL=
RUN npm run build

# ---- 运行阶段：nginx 托管静态产物 ----
FROM nginx:alpine

# 覆盖默认站点配置（含 /api 反代 + SPA 回退）
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
