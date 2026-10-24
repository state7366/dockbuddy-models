#!/usr/bin/env bash
# deploy/models/caver/setup.sh —— CAVER 3.0 通道分析 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[caver] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
# (无 pip 依赖)

# apt 依赖
sudo apt-get install -y default-jre-headless

# 资源落位(assets -> 标准目录)
# 解压到 /home/ubuntu/caver/, 入口 caver.ui.Launcher。

echo "[caver] setup 完成。详见 README.md 验证命令。"
