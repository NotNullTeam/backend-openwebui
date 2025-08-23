#!/usr/bin/env bash

# 数据库迁移检查
echo "运行数据库迁移检查..."
python scripts/migration_manager.py check
if [ $? -ne 0 ]; then
    echo "⚠️  数据库迁移检查发现问题，但继续启动服务..."
    echo "建议运行: python scripts/migration_manager.py fix-all"
fi

# 运行Redis检查脚本（可通过ENABLE_REDIS_CHECK=false禁用）
bash scripts/docker_manager.sh

export CORS_ALLOW_ORIGIN="http://localhost:5173"
export FORWARDED_ALLOW_IP="*"
export USER_AGENT="${USER_AGENT:-OpenWebUI/1.0}"
PORT="${PORT:-8080}"
uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --reload
