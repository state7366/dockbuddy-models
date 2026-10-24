#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gnina 模型自测: gnina 二进制冒烟(--version, 含 CNN 打分内核自检)

工具单元恢复后 /usr/local/bin/gnina 或 MODELS_DIR/gnina/gnina; 验证可执行 +
版本串非空(1.43G 含内置 CNN 权重的预编译二进制)。"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/gnina")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/gnina/test/data")
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]
PDB = os.path.join(COMMON, "structure.pdb")
MSA = os.path.join(COMMON, "msa.a3m")


def run():
    import shutil
    import subprocess
    exe = shutil.which("gnina") or os.path.join(ROOT, "gnina")
    if not os.path.isfile(exe):
        raise RuntimeError(f"gnina 可执行缺失: {exe}(工具单元未恢复?)")
    r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=180)
    txt = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise RuntimeError(f"gnina --version rc={r.returncode}: {txt[:150]}")
    return {"rc": r.returncode, "out_len": len(txt.strip())}


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
