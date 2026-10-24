#!/usr/bin/env bash
# deploy/models/venusrem/setup.sh —— VenusREM 检索增强突变效应 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[venusrem] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "torch"
pip install -q "fair-esm"
pip install -q "vrh"

# apt 依赖
sudo apt-get install -y (foldseek 官方预编译二进制)

# 资源落位(assets -> 标准目录)
# ESM-2 骨干用 _common 的 esm2_t33_650M_UR50D.pt。

echo "[venusrem] setup 完成。详见 README.md 验证命令。"
