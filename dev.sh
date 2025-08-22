#!/bin/bash

# 设置 MSYS2/Cygwin 兼容性变量
# export MSYS_NO_PATHCONV=1
# export MSYS="winsymlinks:nativestrict"
# export CYGWIN="nodosfilewarning"

# 设置环境变量
export CORS_ALLOW_ORIGIN="http://localhost:5173"
export FORWARDED_ALLOW_IP="*"
export USER_AGENT="OpenWebUI/1.0 (AI Competition Project)"
export LANGCHAIN_USER_AGENT="OpenWebUI/1.0 (AI Competition Project)"

# 设置端口
PORT="${PORT:-8080}"

# 使用 winpty 来避免终端问题（如果可用）
# if command -v winpty >/dev/null 2>&1; then
#     winpty uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --reload
# else
    uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --reload
# fi

