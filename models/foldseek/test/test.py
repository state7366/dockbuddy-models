#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""foldseek 模型自测: foldseek 版本 + WT fasta 自检索(easy-search 真跑一次)

自检索命中数 >=1 验证搜索/打分/临时目录写盘全链路(SaProt 结构 token 与
venusrem MSA 检索的共享依赖)。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/foldseek")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/foldseek/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import subprocess
    r = subprocess.run(["foldseek", "version"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"foldseek version rc={r.returncode}")
    ver = r.stdout.strip()
    # foldseek 是**结构**检索工具, 输入必须是 PDB(fasta 会报 No structures found,
    # wave1 冲刺实踩); 用公共 WT 结构做自检索。
    pdb = os.path.join(COMMON, "structure.pdb")
    out_tsv = "/tmp/foldseek_selftest"
    r2 = subprocess.run(["foldseek", "easy-search", pdb, pdb,
                         out_tsv, "/tmp/foldseek_tmp",
                         "--threads", "2"], capture_output=True, text=True, timeout=600)
    hits = 0
    # foldseek 对无后缀输出路径会自动加 .m8 后缀(tsv 缺省格式)——wave1 冲刺踩:
    # 输出实际在 <out>.m8, 不是 <out>。
    for cand in (out_tsv, out_tsv + ".m8"):
        if os.path.isfile(cand):
            with open(cand) as f:
                hits = sum(1 for ln in f if ln.strip())
            break
    if r2.returncode != 0 or hits < 1:
        raise RuntimeError(f"easy-search rc={r2.returncode} hits={hits}: "
                           f"{(r2.stderr or '')[:150]}")
    return {"version_len": len(ver), "self_hits": hits}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
