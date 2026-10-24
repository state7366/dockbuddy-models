#!/usr/bin/env bash
# deploy/models/evmutation/setup.sh —— EVmutation 上位性(DCA) 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[evmutation] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "evcouplings"

# apt 依赖
sudo apt-get install -y cmake
sudo apt-get install -y build-essential

# 资源落位(assets -> 标准目录)
# plmc 源码编译后二进制落位 /usr/local/bin/plmc。

echo "[evmutation] setup 完成。详见 README.md 验证命令。"
