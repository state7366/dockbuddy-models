#!/usr/bin/env bash
# deploy/run_eve.sh —— EVE 家族 VAE 训练 + 突变进化指数打分(云 GPU 实例)
# =============================================================================
# EVE(Frazer 2021)用贝叶斯 VAE 建模家族序列分布, 突变效应 = ΔELBO。
# 无预训练权重 —— 需在本家族深 MSA 上训练(6417 条 × 250 aa)。
#
# 用法(在已装 torch 的 GPU 实例, EVE repo 已上传到 /home/ubuntu/dockbuddy/work/eve):
#   cd /home/ubuntu/dockbuddy/work/eve && bash run_eve.sh
# 依赖: torch + pandas + numpy(无其他重型依赖; EVE 是纯 torch VAE)
# =============================================================================
set -uo pipefail
WORK="${EVE_WORK:-/home/ubuntu/dockbuddy/work/eve}"
cd "$WORK" || exit 1
export PYTHONUTF8=1
# torch 环境: EVE 是纯 torch VAE, 只需 torch+pandas+numpy → 用系统 python3(3.10, 自带
# torch 2.5.1+cu121)。不依赖 geostab conda 环境(可能未就绪)。EVE_PYTHON 可覆盖。
PYTHON="${EVE_PYTHON:-python3}"
export PYTHONPATH="$WORK:${PYTHONPATH:-}"

DATA="$WORK/data"
MSA_FOLDER="$DATA/MSA"
MSA_LIST="$DATA/mappings/pbatase_mapping.csv"
WEIGHTS="$DATA/weights"
CKPT="$WORK/results/VAE_parameters"
LOGS="$WORK/logs"
PARAMS="$DATA/model_params_fast.json"
MUTS_DIR="$DATA/mutations"
mkdir -p "$WEIGHTS" "$CKPT" "$LOGS"

echo "==== 1. 训练 VAE(100000 步) ===="
"$PYTHON" train_VAE.py \
  --MSA_data_folder "$MSA_FOLDER" \
  --MSA_list "$MSA_LIST" \
  --protein_index 0 \
  --MSA_weights_location "$WEIGHTS" \
  --theta_reweighting 0.2 \
  --VAE_checkpoint_location "$CKPT" \
  --model_name_suffix pbatase_fast \
  --model_parameters_location "$PARAMS" \
  --training_logs_location "$LOGS" \
  --seed 42

echo "==== 2. 算进化指数(12 突变) ===="
"$PYTHON" compute_evol_indices.py \
  --MSA_data_folder "$MSA_FOLDER" \
  --MSA_list "$MSA_LIST" \
  --protein_index 0 \
  --MSA_weights_location "$WEIGHTS" \
  --theta_reweighting 0.2 \
  --VAE_checkpoint_location "$CKPT" \
  --model_name_suffix pbatase_fast \
  --model_parameters_location "$PARAMS" \
  --computation_mode input_mutations_list \
  --mutations_location "$MUTS_DIR" \
  --output_evol_indices_location "$WORK/results" \
  --output_evol_indices_filename_suffix pbatase \
  --num_samples_compute_evol_indices 2000 \
  --batch_size 256

echo "==== 完成 ===="
ls -la "$WORK/results/"
