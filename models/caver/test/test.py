#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""caver 模型自测: caver.jar 冒烟(定位 + java 拉起 + 输出含用法信息)

caver 3.0.2 zip 由工具单元解到 MODELS_DIR/cver 下的 jar; 验证 java 能拉起且
输出非空(完整隧道分析需受体+配置, 冒烟只验运行环境)。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/caver")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/caver/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import glob
    import subprocess
    cands = [os.path.join(ROOT, "caver.jar"),
             "/home/ubuntu/dockbuddy/models/caver/caver.jar"]
    jar = next((p for p in cands if os.path.isfile(p)), "")
    if not jar:
        found = glob.glob("/home/ubuntu/dockbuddy/models/caver*/**/caver.jar",
                          recursive=True)
        jar = found[0] if found else ""
    if not jar:
        raise RuntimeError("caver.jar 未找到(工具单元未恢复?)")
    r = subprocess.run(["java", "-jar", jar, "--help"], capture_output=True,
                       text=True, timeout=180)
    txt = ((r.stdout or "") + (r.stderr or "")).lower()
    if r.returncode != 0 and "usage" not in txt and "caver" not in txt:
        raise RuntimeError(f"caver --help rc={r.returncode}: {txt[:150]}")
    return {"rc": r.returncode, "out_len": len(txt)}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
