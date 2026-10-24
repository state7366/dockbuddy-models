#!/usr/bin/env bash
# deploy/models/esm1v/setup.sh —— ESM-1v zero-shot 打分 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[esm1v] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "torch"
pip install -q "fair-esm"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# 权重由 fair-esm 自动下载到 torch hub 缓存(受 TORCH_HOME 控制); 无需手动落位。

echo "[esm1v] setup 完成。详见 README.md 验证命令。"
