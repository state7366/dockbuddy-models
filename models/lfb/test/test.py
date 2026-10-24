#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lfb 模型自测脚本(实例端执行)
===================================================================================
由 deploy/run_model_tests.py 调度: 本目录被上传到 /home/ubuntu/dockbuddy/work/models/lfb/test/ 后执行。

约定(所有模型一致):
  - 环境变量: COMMON_DATA = 公共测试数据目录(/home/ubuntu/dockbuddy/work/models/_common/test/data)
              MODEL_ROOT  = 本模型权重/资源目录(/home/ubuntu/dockbuddy/models/lfb)
              TEST_DATA   = 本模型自带数据目录(/home/ubuntu/dockbuddy/work/models/lfb/test/data)
  - 输出: **最后一行**打印单行 JSON, 形如
              {"scores": {"F205G": 0.12, ...}}   成功
              {"error": "RuntimeError: ..."}        失败
    调度器取最后一行解析, 与 test/baseline.json 比对判回归。
  - 本脚本只依赖本目录 + COMMON_DATA + MODEL_ROOT, 不依赖其他模型的内部路径。
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/lfb")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/lfb/test/data")
# REPO = 本模型 model.json 的 repo.dest;  REPOS = extra_repos 声明的 {别名: 路径}
# 均由调度器按 model.json 注入 —— 测试脚本内不硬编码任何跨模型路径。
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import random
    from scoring.lfb import score_variants
    # lfb 基线口径(tools/run_lfb_local.py): eve a2m(6417条) → 去插入+gap填充
    # → 采样 500(seed42) → esm2_t6_8M。之前误用 650M + 前200条 raw a2m, 数值不对。
    a2m = os.path.join(DATA, "family.a2m")
    seqs, cur = [], []
    for line in open(a2m, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if line.startswith(">"):
            if cur:
                seqs.append("".join(cur)); cur = []
        else:
            cur.append(line)
    if cur:
        seqs.append("".join(cur))
    out = []
    for s in seqs:
        s2 = "".join(c for c in s if c.isupper() or c in "-.")
        if len(s2) != len(WT):
            continue
        out.append("".join(WT[i] if s2[i] in "-." else s2[i] for i in range(len(s2))))
    random.seed(42)
    if len(out) > 500:
        out = [out[0]] + random.sample(out[1:], 499)
    return score_variants(WT, VAR, family_seqs=out,
                          model_name="esm2_t6_8M_UR50D", device="cpu")


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
