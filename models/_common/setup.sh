#!/usr/bin/env bash
# deploy/models/_common/setup.sh —— 共享资源(ESM-2 骨干 + conda) 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[_common] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
# (无 pip 依赖)

# apt 依赖
# (无 apt 依赖)

# 资源落位(assets -> 标准目录)
# esm2 权重落位 /home/ubuntu/dockbuddy/models/esm2/ 或 torch hub 缓存 /root/.cache/torch/hub/checkpoints/。

echo "[_common] setup 完成。详见 README.md 验证命令。"
