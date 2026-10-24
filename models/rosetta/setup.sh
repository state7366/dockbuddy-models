#!/usr/bin/env bash
# deploy/models/rosetta/setup.sh —— PyRosetta 精细 ΔΔG 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[rosetta] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
# (无 pip 依赖)

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# pip install --no-index --find-links . pyrosetta(用 assets 里的 wheel)。

echo "[rosetta] setup 完成。详见 README.md 验证命令。"
