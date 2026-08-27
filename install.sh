#!/usr/bin/env bash
# ====================================================================
# llm-plan-warmer 服务器一键安装器
#
# 用法:
#   curl -fsSL https://raw.githubusercontent.com/supertiny99/llm-plan-warmer/master/install.sh | bash
#   # 或带智谱 API Key 直装 (生成最小单账号配置):
#   curl -fsSL https://raw.githubusercontent.com/supertiny99/llm-plan-warmer/master/install.sh | bash -s -- --key <API_KEY>
#   # 或手动 clone 后运行:
#   git clone https://github.com/supertiny99/llm-plan-warmer.git && cd llm-plan-warmer && bash install.sh
#
# 选项:
#   --dir <路径>      安装目录 (默认 ~/llm-plan-warmer；在仓库内运行时默认取当前目录)
#   --key <KEY>       用单个智谱 API Key 生成最小 .env (已有 .env 时忽略)
#   --anchors <列表>  预热锚点，北京时间 "HH:MM,HH:MM,..." (默认 "07:20,12:40,18:00,23:20")
#   --print-cron      只打印将安装的 crontab 行，不写入
#   --no-cron         只安装文件与依赖，不安装 crontab
#   --uninstall       摘除 crontab 条目 (不删除文件与 .env)
#
# 说明:
#   - warmer.py 按北京时间整点匹配 trigger_hours，本脚本会把锚点换算成
#     服务器本地时区写入 crontab；服务器时区使用夏令时的话，换季后需重跑本脚本。
#   - 重复运行 = 更新: git pull + 依赖升级 + 幂等刷新 crontab (.env 保持不动)。
# ====================================================================
set -euo pipefail

REPO_URL="https://github.com/supertiny99/llm-plan-warmer.git"
REPO_TARBALL="https://github.com/supertiny99/llm-plan-warmer/archive/refs/heads/master.tar.gz"
CRON_BEGIN="# >>> llm-plan-warmer begin >>>"
CRON_END="# <<< llm-plan-warmer end <<<"
DEFAULT_ANCHORS="07:20,12:40,18:00,23:20"

INSTALL_DIR=""
API_KEY=""
ANCHORS="$DEFAULT_ANCHORS"
PRINT_CRON=0
NO_CRON=0
UNINSTALL=0

say()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

usage() { cat <<'EOF'
用法: bash install.sh [选项]
  --dir <路径>      安装目录 (默认 ~/llm-plan-warmer；在仓库内运行时默认取当前目录)
  --key <KEY>       用单个智谱 API Key 生成最小 .env (已有 .env 时忽略)
  --anchors <列表>  预热锚点，北京时间 "HH:MM,HH:MM,..." (默认 "07:20,12:40,18:00,23:20")
  --print-cron      只打印将安装的 crontab 行，不写入
  --no-cron         只安装文件与依赖，不安装 crontab
  --uninstall       摘除 crontab 条目 (不删除文件与 .env)
  -h | --help       显示本帮助
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dir)       INSTALL_DIR="${2:-}"; shift 2 ;;
    --key)       API_KEY="${2:-}"; shift 2 ;;
    --anchors)   ANCHORS="${2:-}"; shift 2 ;;
    --print-cron) PRINT_CRON=1; shift ;;
    --no-cron)   NO_CRON=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) die "未知参数: $1 (见 --help)" ;;
  esac
done

# ---------- 卸载: 只摘 crontab 块 ----------
if [ "$UNINSTALL" = 1 ]; then
  if command -v crontab >/dev/null 2>&1; then
    strip_old_block() { awk -v b="$CRON_BEGIN" -v e="$CRON_END" \
      'index($0,b){skip=1} !skip{print} index($0,e){skip=0}' ; }
    cur=$(crontab -l 2>/dev/null | strip_old_block || true)
    printf '%s\n' "$cur" | crontab - 2>/dev/null || true
    say "已摘除 crontab 中的 llm-plan-warmer 条目。"
  else
    warn "未找到 crontab 命令，请手动删除 crontab 中 ${CRON_BEGIN} 与 ${CRON_END} 之间的行。"
  fi
  say "文件与 .env 未删除，如需彻底清理请手动: rm -rf <安装目录>"
  exit 0
fi

# ---------- 计算服务器本地时区的 cron 时间 ----------
# warmer.py 以北京时间 (UTC+8) 整点匹配 trigger_hours，锚点必须换算到服务器本地时间
offset=$(date +%z | tr -d ':')
if [[ "$offset" =~ ^[+-][0-9]{4}$ ]]; then
  sign=${offset:0:1}
  offmin=$(( (10#${offset:1:2}) * 60 + 10#${offset:3:2} ))
  [ "$sign" = "-" ] && offmin=$(( -offmin ))
else
  warn "无法识别服务器时区偏移 ($offset)，cron 时间直接使用北京时间。"
  offmin=$(( 8 * 60 ))
fi

cron_lines=""
bjt_list=""
IFS=',' read -ra ANCHOR_ARR <<< "$ANCHORS"
for a in "${ANCHOR_ARR[@]}"; do
  a=$(echo "$a" | tr -d ' ')
  [[ "$a" =~ ^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$ ]] || die "锚点格式错误: $a (应为 HH:MM 逗号分隔)"
  bh=${a%%:*}; bm=${a##*:}
  total=$(( (10#$bh * 60 + 10#$bm - 8 * 60 + offmin + 1440) % 1440 ))
  lh=$(( total / 60 )); lm=$(( total % 60 ))
  cron_lines+="$lm $lh * * * PLACEHOLDER_RUNSH"$'\n'
  bjt_list+="$a "
done

if [ "$PRINT_CRON" = 1 ]; then
  printf '%s\n' "${cron_lines//PLACEHOLDER_RUNSH/<安装目录>\/run.sh}"
  exit 0
fi

# ---------- 预检 ----------
command -v python3 >/dev/null 2>&1 || die "未找到 python3，请先安装 Python >= 3.8"
pyver=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
[ "$(printf '%s\n' "3.8" "$pyver" | sort -V | head -n1)" = "3.8" ] \
  || die "需要 Python >= 3.8，当前为 $pyver"
say "Python 版本: $pyver"

command -v git >/dev/null 2>&1 && HAS_GIT=1 || HAS_GIT=0
command -v curl >/dev/null 2>&1 && HAS_CURL=1 || HAS_CURL=0
[ "$HAS_GIT" = 1 ] || [ "$HAS_CURL" = 1 ] || die "未找到 git 或 curl，无法下载仓库"

if [ "$(id -u)" = 0 ]; then
  warn "正在以 root 运行，将安装到 /root 下并写入 root 的 crontab。"
fi

# ---------- 确定安装目录并下载 ----------
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo .)
IN_REPO=0
if [ -f "$SCRIPT_DIR/warmer.py" ] && [ -f "$SCRIPT_DIR/requirements.txt" ]; then
  IN_REPO=1
fi
if [ -z "$INSTALL_DIR" ]; then
  if [ "$IN_REPO" = 1 ]; then INSTALL_DIR="$SCRIPT_DIR"; else INSTALL_DIR="$HOME/llm-plan-warmer"; fi
fi
case "$INSTALL_DIR" in
  *\ *) die "安装目录含空格，cron 无法可靠调用: $INSTALL_DIR" ;;
esac
say "安装目录: $INSTALL_DIR"

if [ "$IN_REPO" != 1 ] || [ "$INSTALL_DIR" != "$SCRIPT_DIR" ]; then
  if [ -d "$INSTALL_DIR/.git" ]; then
    say "目录已存在，执行更新: git pull"
    git -C "$INSTALL_DIR" pull --ff-only || warn "git pull 失败，继续使用现有代码。"
  elif [ "$HAS_GIT" = 1 ]; then
    say "克隆仓库..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  else
    say "无 git，使用 curl 下载 tarball..."
    mkdir -p "$INSTALL_DIR"
    curl -fsSL "$REPO_TARBALL" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
  fi
fi
[ -f "$INSTALL_DIR/warmer.py" ] || die "下载失败: $INSTALL_DIR/warmer.py 不存在"
chmod +x "$INSTALL_DIR/run.sh" 2>/dev/null || true

# ---------- 虚拟环境与依赖 ----------
cd "$INSTALL_DIR"
if python3 -m venv venv 2>/dev/null; then
  PYBIN="$INSTALL_DIR/venv/bin/python"
  say "安装依赖到 venv..."
  "$INSTALL_DIR/venv/bin/pip" install --quiet -r requirements.txt
else
  warn "python3 -m venv 不可用 (Debian 系可能缺 python3-venv)，回退 pip3 --user"
  pip3 install --user --quiet -r requirements.txt
  PYBIN="python3"
fi
say "依赖安装完成。"

# ---------- 生成 .env ----------
if [ -f .env ]; then
  say "检测到已有 .env，保持不动。"
elif [ -n "$API_KEY" ]; then
  cat > .env <<EOF
# 由 install.sh --key 生成于 $(date '+%Y-%m-%d %H:%M:%S')
# 更多多供应商/多 Key 配置见 .env.example
LLM_ACCOUNTS='[
  {
    "name": "智谱 Coding Plan",
    "api_key": "$API_KEY",
    "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
    "model": "glm-4.7",
    "trigger_hours": [7, 12, 18, 23],
    "avoid_weekday_peak": true
  }
]'
EOF
  say "已用 --key 生成最小单账号 .env。"
elif [ -f .env.example ]; then
  cp .env.example .env
  ENV_FROM_TEMPLATE=1
  say "已从模板生成 .env，稍后请编辑填入真实 Key。"
else
  warn "未找到 .env.example，请参考 README 手动创建 .env。"
fi
[ -f .env ] && chmod 600 .env

# ---------- 组装 crontab 块 ----------
cron_block="${CRON_BEGIN}
# 预热锚点(北京时间): ${bjt_list% }
# 已按服务器时区 $(date +%Z) (UTC偏移 ${offset}) 换算；夏令时时区换季后请重跑 install.sh
${cron_lines//PLACEHOLDER_RUNSH/$INSTALL_DIR\/run.sh}${CRON_END}"

# ---------- 写入 crontab ----------
if [ "$NO_CRON" != 1 ]; then
  if command -v crontab >/dev/null 2>&1; then
    strip_old_block() { awk -v b="$CRON_BEGIN" -v e="$CRON_END" \
      'index($0,b){skip=1} !skip{print} index($0,e){skip=0}' ; }
    cur=$(crontab -l 2>/dev/null | strip_old_block || true)
    printf '%s\n' "$cur" "$cron_block" | crontab -
    say "crontab 已安装 (服务器本地时间，对应北京时间锚点: ${bjt_list% })。"
  else
    warn "未找到 crontab 命令，请手动将以下行加入计划任务:"
    printf '%s\n' "$cron_block"
  fi
fi

# ---------- 配置校验 ----------
say "运行配置校验 (--dry-run，不发送任何请求)..."
"$PYBIN" warmer.py --dry-run || warn "配置校验未通过，请检查 .env 后重试。"

# ---------- 摘要 ----------
printf '\n'
say "================ 安装完成 ================"
say "安装目录 : $INSTALL_DIR"
say "配置文件 : $INSTALL_DIR/.env (chmod 600)"
say "运行日志 : $INSTALL_DIR/logs/warmer.log"
say "手动执行 : $INSTALL_DIR/run.sh"
say "配置校验 : cd $INSTALL_DIR && $PYBIN warmer.py --dry-run"
say "更新     : 重新运行本安装脚本 (保留 .env)"
say "卸载     : bash $INSTALL_DIR/install.sh --uninstall"
if [ "${ENV_FROM_TEMPLATE:-0}" = 1 ]; then
  printf '\n'
  warn "下一步: 编辑 $INSTALL_DIR/.env 填入真实 API Key 后，运行上面的校验命令确认配置。"
fi
printf '\n'
