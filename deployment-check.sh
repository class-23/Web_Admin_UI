#!/bin/bash
# QuantClaw 部署检查脚本

echo "=== QuantClaw 部署状态检查 ==="
echo

# 检查环境文件
if [ -f ".env" ]; then
    echo "✅ .env 文件存在"
else
    echo "❌ .env 文件缺失，请复制 .env.example 并配置"
    exit 1
fi

# 检查关键环境变量
echo
echo "=== 环境变量检查 ==="
check_env_var() {
    local var_name=$1
    local var_value=$(grep "^$var_name=" .env | cut -d'=' -f2)
    if [ -n "$var_value" ]; then
        echo "✅ $var_name: $var_value"
    else
        echo "❌ $var_name: 未设置"
    fi
}

check_env_var "PG_PASSWORD"
check_env_var "JWT_SECRET"
check_env_var "APP_PORT"

# 检查Docker状态
echo
echo "=== Docker 状态检查 ==="
if command -v docker &> /dev/null; then
    echo "✅ Docker 已安装"
    if docker info &> /dev/null; then
        echo "✅ Docker 服务运行正常"
    else
        echo "❌ Docker 服务未运行"
    fi
else
    echo "❌ Docker 未安装"
fi

# 检查Docker Compose
echo
echo "=== Docker Compose 状态检查 ==="
if command -v docker-compose &> /dev/null; then
    echo "✅ Docker Compose 已安装"
elif docker compose version &> /dev/null; then
    echo "✅ Docker Compose (plugin) 已安装"
else
    echo "❌ Docker Compose 未安装"
fi

# 检查端口占用
echo
echo "=== 端口占用检查 ==="
APP_PORT=$(grep "^APP_PORT=" .env | cut -d'=' -f2)
APP_PORT=${APP_PORT:-8082}
if netstat -tuln 2>/dev/null | grep -q ":$APP_PORT "; then
    echo "⚠️  端口 $APP_PORT 已被占用"
else
    echo "✅ 端口 $APP_PORT 可用"
fi

# 检查数据库连接
echo
echo "=== 数据库连接检查 ==="
PG_PORT=$(grep "^PG_PORT=" .env | cut -d'=' -f2)
PG_PORT=${PG_PORT:-5433}
if netstat -tuln 2>/dev/null | grep -q ":$PG_PORT "; then
    echo "✅ 数据库端口 $PG_PORT 正在监听"
else
    echo "⚠️  数据库端口 $PG_PORT 未监听"
fi

echo
echo "=== 建议操作 ==="
echo "1. 确保所有环境变量已正确设置"
echo "2. 检查防火墙设置，确保端口开放"
echo "3. 验证数据库连接配置"
echo "4. 查看容器日志: docker-compose logs"
echo "5. 检查容器状态: docker-compose ps"
echo

echo "=== 常用命令 ==="
echo "启动服务: docker-compose up -d"
echo "查看日志: docker-compose logs -f"
echo "停止服务: docker-compose down"
echo "重启服务: docker-compose restart"
echo "进入容器: docker-compose exec app bash"