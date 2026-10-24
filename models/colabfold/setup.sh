#!/usr/bin/env bash
# deploy/models/colabfold/setup.sh —— ColabFold 折叠 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[colabfold] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "colabfold==1.6.3"
pip install -q "nvidia-cudnn-cu12==9.8.0.87"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# 权重解压到 ~/.cache/colabfold/params(需 touch download_complexes_multimer_v3_finished.txt)。

echo "[colabfold] setup 完成。详见 README.md 验证命令。"
