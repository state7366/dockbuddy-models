#!/usr/bin/env bash
# deploy/models/saprot/setup.sh —— SaProt 结构感知 PLM 部署（幂等）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"

echo "[saprot] 目标: $MODELS_DIR"

# pip 依赖(能 pip 装的走这里, 不进 assets)
pip install -q "torch"
pip install -q "transformers==4.28.0"
pip install -q "pytorch-lightning==1.8.3"
pip install -q "torchmetrics==0.9.3"
pip install -q "easydict"
pip install -q "lmdb"
pip install -q "pooch"
pip install -q "accelerate"

# apt 依赖
sudo apt-get install -y (foldseek 用官方预编译二进制)

# 资源落位(assets -> 标准目录)
# 权重落位 /home/ubuntu/dockbuddy/repos/SaProt/weights/SaProt/SaProt_650M_AF2/(pytorch_model.bin + .pt); saprot_repo 提供 config/vocab/tokenizer。

echo "[saprot] setup 完成。详见 README.md 验证命令。"
