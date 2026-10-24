#!/usr/bin/env bash
# deploy/models/esmfold/setup.sh —— ESMFold 折叠 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[esmfold] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "fair-esm[esmfold]"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# esmfold_3B_v1.pt 落位 torch hub 缓存; openfold/dllogger 先 pip install ./dllogger 再 pip install --no-deps ./openfold。

echo "[esmfold] setup 完成。详见 README.md 验证命令。"
