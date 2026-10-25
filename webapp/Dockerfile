# 后端镜像：FastAPI + uvicorn
# 构建上下文为仓库根目录（docker-compose 指定 context: .），故路径以 webapp/ 开头。
FROM python:3.11-slim

WORKDIR /app

# 仅先拷贝依赖清单，利用 Docker 层缓存
COPY webapp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端代码（webapp/ 作为包存在，以便 `uvicorn webapp.main:app`）
COPY webapp/ ./webapp/

EXPOSE 8005

CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8005"]
