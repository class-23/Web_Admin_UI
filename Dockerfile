FROM python:3.11-slim

# 安装 PostgreSQL 客户端库和 curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建 runtime 目录（SQLite 配置库）
RUN mkdir -p runtime

EXPOSE 8082

CMD ["python", "main.py"]
