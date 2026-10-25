#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""promep 模型自测: ProMEP import 冒烟(预期 FAIL —— 权重不公开, 封堵态)

ProMEP(drlnet/dmsnet.pth 无公开下载 + SE(3) 栈绑 torch 1.13)处于封堵态, 本
冒烟用于在封堵解除时一键确认恢复; 当前预期报错即正确行为。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/promep")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/promep/test/data")
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
        importlib.import_module("dockbuddy_scoring.promep")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"dockbuddy_scoring.promep 加载失败(封堵态预期): "
                           f"{type(e).__name__}: {e}")
    return {"adapter_import": 1}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
