#!/usr/bin/env bash
# deploy/models/evolvepro/setup.sh —— EvolvePro few-shot 导出 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[evolvepro] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "xgboost"
pip install -q "scikit-learn-extra"
pip install -q "fair-esm"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# EvolvePro/ 落位 /home/ubuntu/EvolvePro/。

echo "[evolvepro] setup 完成。详见 README.md 验证命令。"
