#!/usr/bin/env bash
# deploy/models/promep/setup.sh —— ProMEP 多模态零样本适应度 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[promep] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "torch"

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# 仓库 ProMEP/ 即代码; 权重另需。

echo "[promep] setup 完成。详见 README.md 验证命令。"
