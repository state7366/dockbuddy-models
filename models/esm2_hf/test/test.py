#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""esm2_hf 模型自测: HF 格式 ESM-2 650M 骨干(VenusREM 共享)本地加载 + embedding

transformers AutoModel 从本地 ROOT(config+model.safetensors)加载, 对 WT 序列做
前向, 验收表征维度 1280 与序列长 252。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/esm2_hf")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/esm2_hf/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(ROOT)
    mdl = AutoModel.from_pretrained(ROOT)
    mdl.eval()
    batch = tok(WT, return_tensors="pt")
    with torch.no_grad():
        rep = mdl(**batch).last_hidden_state[0, 1:-1, :]
    return {"dim": int(rep.shape[-1]), "len": int(rep.shape[0]),
            "mean": round(float(rep.mean()), 4)}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
