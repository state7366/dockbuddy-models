#!/usr/bin/env bash
# deploy/models/ortholog/setup.sh —— OrthologTransformer 跨物种基因重设计 部署（幂等）
# 用法: sudo bash setup.sh   (或 DOCK_MODELS_DIR=/path bash setup.sh)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS_DIR="${DOCK_MODELS_DIR:-/home/ubuntu/dockbuddy/models}"
DEST="$MODELS_DIR/ortholog"

echo "[ortholog] 目标目录: $DEST"

# 1. pip 依赖(推理只需这三个; 实例已有则跳过)
python3 -c "import torch, Bio, numpy" 2>/dev/null && echo "[ortholog] 依赖已装, 跳过" || {
  echo "[ortholog] 安装 pip 依赖(torch>=2.0 biopython numpy)"
  pip install -q "torch>=2.0" biopython numpy
}

# 2. 权重落位(assets -> $DEST)
mkdir -p "$DEST"
for f in aligned_model.pt unaligned_model.pt; do
  if [ -f "$HERE/assets/$f" ]; then
    cp -n "$HERE/assets/$f" "$DEST/$f" && echo "[ortholog] 落位 $f"
  else
    echo "[ortholog][warn] 缺 $HERE/assets/$f (本地 assets 未下载)"
  fi
done

# 3. 自检
python3 - <<PY
import torch, os
f = os.path.join("$DEST", "aligned_model.pt")
if os.path.isfile(f):
    d = torch.load(f, map_location="cpu")
    # 校验超参关键键(dim_feedforward=1024 的 fc_out_1.weight 应为 [512,512])
    assert d["fc_out_1.weight"].shape == (512, 512), f"fc_out_1 形状异常: {d['fc_out_1.weight'].shape}"
    print("[ortholog] 自检通过: aligned_model.pt 可读且超参匹配(dim_feedforward=1024)")
else:
    print("[ortholog][warn] 权重未落位, 跳过硬校验")
PY

echo "[ortholog] setup 完成。用法: dockbuddy ortholog --source-dna <CDS> --source-species MICSL --target-species ECOLI --fixed-aa-len <len>"
