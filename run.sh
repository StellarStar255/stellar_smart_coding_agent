#!/usr/bin/env bash
#
# Stellar 一键启动脚本
#
# 功能：自动创建 venv、安装依赖、检查 .env，然后启动 agent。
# 传给本脚本的参数会原样透传给 stellar，例如：
#   ./run.sh                          # 交互式 REPL
#   ./run.sh --provider openai        # 用 OpenAI
#   ./run.sh -p "帮我写个快排"          # 单次执行
#   ./run.sh --yolo                   # 跳过确认
#
set -euo pipefail

# 切到脚本所在目录，保证相对路径正确
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"

# 1. 没有 venv 就创建
if [ ! -d "$VENV" ]; then
    echo "▸ 未发现虚拟环境，正在创建 $VENV ..."
    python3 -m venv "$VENV"
fi

# 2. 确保依赖已安装（用一个 stamp 文件避免每次都装）
STAMP="$VENV/.deps-installed"
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
    echo "▸ 正在安装/更新依赖 ..."
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r requirements.txt
    touch "$STAMP"
fi

# 3. 检查 .env（不存在则从模板创建并提示填 key）。
#    key 是否有效交给 Python 端校验——它会给出清晰的报错。
if [ ! -f ".env" ]; then
    echo "▸ 未发现 .env，已从模板创建。"
    cp .env.example .env
    echo "  请编辑 $(pwd)/.env 填入 API key 后重试。"
    exit 1
fi

# 4. 启动（透传所有参数）
echo "▸ 启动 Stellar ..."
exec "$PY" -m stellar "$@"
