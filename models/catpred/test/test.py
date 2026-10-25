#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""catpred 模型自测脚本(实例端执行)
===================================================================================
由 deploy/run_model_tests.py 调度: 本目录被上传到 /home/ubuntu/dockbuddy/work/models/catpred/test/ 后执行。

约定(所有模型一致):
  - 环境变量: COMMON_DATA = 公共测试数据目录(/home/ubuntu/dockbuddy/work/models/_common/test/data)
              MODEL_ROOT  = 本模型权重/资源目录(/home/ubuntu/dockbuddy/models/catpred)
              TEST_DATA   = 本模型自带数据目录(/home/ubuntu/dockbuddy/work/models/catpred/test/data)
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
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/catpred")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/catpred/test/data")
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
    from dockbuddy_scoring.catpred import score_variants
    return score_variants(WT, VAR, repo_dir=REPO,
                          checkpoint_dir=os.path.join(ROOT, "data", "pretrained",
                                                      "production", "kcat"),
                          tarball=os.path.join(ROOT, "checkpoint",
                                               "capsule_data_update.tar.gz"),
                          substrate_smiles="O=C(OCCO)c1ccc(C(=O)OCCO)cc1",
                          structure_dir=os.path.join(DATA, "structures"),
                          use_gpu=True)


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
