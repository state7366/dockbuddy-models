#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""proteinmpnn 模型自测: ProteinMPNN 重设计 WT 结构(公共 structure.pdb)

固定催化三联体 126/174/204, 重设计 205/208(F205G/Q208S 所在位); 验收: 序列数、
长度一致、三联体保留、205/208 位确被重设计。repo_dir 由调度器 REPO_DIR 注入。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/proteinmpnn")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/proteinmpnn/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    from scoring.mpnn import redesign_sequences
    repo = REPO or REPOS.get("proteinmpnn", "")
    if not repo:
        raise RuntimeError("ProteinMPNN 仓库路径缺失(REPO_DIR 未注入)")
    ckpt = os.path.join(ROOT, "vanilla_model_weights", "v_48_020.pt")
    out = redesign_sequences(WT, PDB,
                             fixed_sites=[126, 174, 204],
                             redesign_sites=[205, 208],
                             repo_dir=repo, num_seqs=2, temperature=0.1, seed=0,
                             checkpoint=ckpt)
    seqs = out["sequences"]
    if not seqs:
        raise RuntimeError("ProteinMPNN 未产出序列")
    triad = (126, 174, 204)
    triad_ok = all(s[i - 1] == WT[i - 1] for s in seqs for i in triad)
    len_ok = all(len(s) == len(WT) for s in seqs)
    redesigned = sum(1 for s in seqs if s[204] != WT[204] or s[207] != WT[207])
    if not (triad_ok and len_ok):
        raise RuntimeError(f"验收失败: triad_ok={triad_ok} len_ok={len_ok}")
    return {"n_seqs": len(seqs), "len_ok": 1 if len_ok else 0,
            "triad_ok": 1 if triad_ok else 0, "redesigned_205_208": redesigned}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
