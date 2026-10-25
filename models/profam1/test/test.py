#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""profam1 模型自测: ProFam-1 家族条件打分(WT + F205G/Q208T/F205S/Q208S)

公共 MSA 取前 64 条做家族条件, checkpoint 用 model.json 权重通道拉下的
assets/checkpoints/last.ckpt; env=profam(transformers<5, 独立 conda 环境)。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/profam1")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/profam1/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def _family_from_a3m(path: str, limit: int = 64) -> list:
    """公共 MSA(a3m) → 家族序列列表(与 WT 等长才算对齐; profam 的 hamming
    相似度要求 prompt 序列与 query 同长——含插入/缺端的同源序列会致
    broadcast 253 vs 252 失败, wave1 冲刺实踩)。"""
    seqs, cur = [], []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln.startswith(">"):
                if cur:
                    seqs.append("".join(cur))
                    cur = []
            elif ln:
                cur.append(ln)
    if cur:
        seqs.append("".join(cur))
    keep = set("ARNDCQEGHILKMFPSTWYV-")
    out = []
    for s in seqs:
        s = "".join(ch for ch in s.upper() if ch in keep)
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def run():
    import torch
    from dockbuddy_scoring.profam import score_variants
    fam = _family_from_a3m(MSA, limit=64)
    wt_len = len(WT)
    fam_aligned = [s for s in fam if len(s) == wt_len]
    if len(fam_aligned) < 8:
        raise RuntimeError(f"等长家族序列不足: {len(fam_aligned)}/{len(fam)}"
                           f"(MSA 对齐质量差?)")
    ckpt = os.path.join(ROOT, "assets", "checkpoints", "last.ckpt")
    if not os.path.isfile(ckpt):
        raise RuntimeError(f"checkpoint 缺失(权重未拉?): {ckpt}")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    return score_variants(WT, VAR, family_seqs=fam_aligned, checkpoint=ckpt,
                          device=dev, ensemble_size=2)


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
