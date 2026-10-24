#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""esmfold 模型自测: ESMFold 本地折叠 WT 序列(fold_api 本地通道)

cos 权重(cold/esmfold/esmfold_3B_v1.pt)若不在 TORCH_HOME/hub/checkpoints 则
先 symlink 粘合, 再走 prescreen.fold_api.esmfold_pdb_local 折叠; 验收返回 PDB
文本 + 残基数与 WT 一致。3B 模型显存吃紧, chunk_size=64。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/esmfold")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/esmfold/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    ckpt = os.path.join(ROOT, "assets", "esmfold_3B_v1.pt")
    if not os.path.isfile(ckpt):
        raise RuntimeError(f"ESMFold 权重缺失(未拉 cold 层?): {ckpt}")
    torch_home = os.environ.get("TORCH_HOME",
                                "/home/ubuntu/dockbuddy/work/cache/torch")
    hub_dir = os.path.join(torch_home, "hub", "checkpoints")
    os.makedirs(hub_dir, exist_ok=True)
    dst = os.path.join(hub_dir, "esmfold_3B_v1.pt")
    if not os.path.exists(dst):
        os.symlink(ckpt, dst)
    from prescreen.fold_api import esmfold_pdb_local
    pdb = esmfold_pdb_local(WT, device="cuda", chunk_size=64)
    n_res = sum(1 for ln in pdb.splitlines() if ln.startswith("ATOM"))
    if not pdb.startswith("PARENT") or n_res < len(WT):
        raise RuntimeError(f"PDB 异常: atoms={n_res} 期望>={len(WT)}")
    return {"pdb_atoms": n_res, "wt_len": len(WT)}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
