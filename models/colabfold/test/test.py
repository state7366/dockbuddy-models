#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""colabfold 模型自测: ColabFold 冒烟(import + AF2 参数包在位性)

colabfold 未进 conda 环境(pip 未装)时本测试记 FAIL, 属「未部署」而非「损坏」——
部署方式(conda/pip + cold 层 AF2 参数)见 model.json notes。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/colabfold")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/colabfold/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    try:
        import colabfold  # noqa: F401
    except ImportError as e:
        raise RuntimeError(f"colabfold 未安装(未部署): {e}")
    params = os.path.join(ROOT, "assets", "alphafold_params_colab_2022-12-06.tar")
    if not os.path.isfile(params):
        raise RuntimeError(f"AF2 参数包缺失(cold 层未拉?): {params}")
    return {"import_ok": 1, "params_mb": round(os.path.getsize(params) / 1e6)}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
