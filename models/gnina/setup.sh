#!/usr/bin/env bash
# deploy/models/gnina/setup.sh —— GNINA CNN 重打分 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[gnina] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "(无, 预编译二进制)"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# 二进制落位 /home/ubuntu/gnina。

echo "[gnina] setup 完成。详见 README.md 验证命令。"
