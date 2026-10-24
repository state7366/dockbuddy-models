#!/usr/bin/env bash
# deploy/models/foldx/setup.sh —— FoldX 5.1 ΔΔG 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[foldx] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
# (无 pip 依赖)

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# foldx/ 目录(foldx_20261231 + rotabase.txt + molecules/)整体落位 /home/ubuntu/foldx/。

echo "[foldx] setup 完成。详见 README.md 验证命令。"
