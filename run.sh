#!/usr/bin/env bash
# llm-plan-warmer cron 包装器: crontab 行统一调用本脚本，
# 负责切换工作目录 (warmer.py 依赖 CWD 下的 .env)、日志轮转与输出落盘。
# 日志重定向收在这里而非 crontab 行内，避免 crontab 对 % 的转义问题。
set -u

cd "$(dirname "$0")" || exit 1

mkdir -p logs
LOG="logs/warmer.log"

# 简单轮转: 超过 5MB 截断，避免长期运行撑爆磁盘
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
  : > "$LOG"
fi

PY="venv/bin/python"
[ -x "$PY" ] || PY="python3"

exec "$PY" warmer.py "$@" >> "$LOG" 2>&1
