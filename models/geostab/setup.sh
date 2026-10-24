#!/usr/bin/env bash
# deploy/models/geostab/setup.sh —— GeoStab GeoDDG/GeoDTm 稳定性 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[geostab] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "torch==1.13"
pip install -q "biopython"
pip install -q "biopandas"
pip install -q "pdb-tools"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# GeoStab/ 仓库落位 /home/ubuntu/GeoStab/; 权重 model_*/model.pt 随仓。

echo "[geostab] setup 完成。详见 README.md 验证命令。"
