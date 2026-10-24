#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mu_protein 模型自测: muformer 适配器 import 冒烟(muformer 独立 env)

µFormer 打分需已训练 checkpoint(train 入口另走), 本冒烟只验适配器与其依赖在
muformer conda 环境(py3.8 + torch 1.13.1 CPU + transformers 4.17)可加载。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/mu_protein")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/mu_protein/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import importlib
    try:
        importlib.import_module("scoring.muformer")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"scoring.muformer 加载失败: {type(e).__name__}: {e}")
    return {"adapter_import": 1}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
