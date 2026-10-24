#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""evolvepro 模型自测: EVOLVEpro 仓库编译冒烟(语法级, 无 import 副作用)

EVOLVEpro 无 pipeline 适配器(主动学习/DBTL 候选, 未接入); 冒烟 = 仓库内全部
.py 可编译 + 源码完整(sourcecode 经 sftp/COS 单元上传后)。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/evolvepro")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/evolvepro/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import py_compile
    import pathlib
    repo = REPO or REPOS.get("evolvepro", "")
    if not repo or not os.path.isdir(repo):
        raise RuntimeError(f"仓库未上传(REPO_DIR={repo!r})")
    n = 0
    for p in pathlib.Path(repo).rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        py_compile.compile(str(p), doraise=True)
        n += 1
    if n == 0:
        raise RuntimeError("仓库无 .py 文件(源码不完整?)")
    return {"compiled_files": n}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
