#!/usr/bin/env bash

# Docker管理脚本
# 检查Docker状态并启动Redis容器

# 检查是否启用Redis
ENABLE_REDIS_CHECK=${ENABLE_REDIS_CHECK:-"true"}
if [[ "${ENABLE_REDIS_CHECK,,}" != "true" ]]; then
    echo "⚠️  ENABLE_REDIS环境变量未设置为true，跳过Redis容器启动"
    echo "应用将使用内存缓存替代Redis"
    exit 0
fi

# 检查Docker是否运行
echo "检查Docker状态..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker未运行，尝试启动Docker Desktop..."
    
    # 尝试启动Docker Desktop (Windows)
    if command -v powershell >/dev/null 2>&1; then
        powershell -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" 2>/dev/null || \
        powershell -Command "Start-Process 'C:\Users\$env:USERNAME\AppData\Local\Programs\Docker\Docker\Docker Desktop.exe'" 2>/dev/null || \
        echo "⚠️  无法自动启动Docker Desktop，请手动启动"
        
        echo "等待Docker启动..."
        for i in {1..30}; do
            if docker info >/dev/null 2>&1; then
                echo "✅ Docker已启动"
                break
            fi
            echo "等待中... ($i/30)"
            sleep 2
        done
        
        if ! docker info >/dev/null 2>&1; then
            echo "❌ Docker启动超时，将跳过Redis容器启动"
            echo "请手动启动Docker Desktop后重新运行脚本"
            echo ""
            return 1
        fi
    fi
fi

# 检查并启动Redis Docker容器
if docker info >/dev/null 2>&1; then
    echo "检查Redis容器状态..."
    if ! docker ps --format "table {{.Names}}" | grep -q "^redis$"; then
        if docker ps -a --format "table {{.Names}}" | grep -q "^redis$"; then
            echo "启动已存在的Redis容器..."
            docker start redis
        else
            echo "创建并启动新的Redis容器..."
            docker run -d --name redis -p 6379:6379 redis:latest
        fi
        echo "等待Redis启动..."
        sleep 3
    else
        echo "Redis容器已在运行"
    fi
    echo "✅ Redis容器准备就绪"
else
    echo "⚠️  Docker未运行，跳过Redis容器启动"
    echo "应用将使用内存缓存替代Redis"
fi
