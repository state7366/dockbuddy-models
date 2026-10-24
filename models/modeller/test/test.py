#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""modeller 模型自测脚本(实例端执行)
===================================================================================
由 deploy/run_model_tests.py 调度: 本目录被上传到
/home/ubuntu/dockbuddy/work/models/modeller/test/ 后执行。

约定(所有模型一致):
  - 环境变量: COMMON_DATA = 公共测试数据目录(/home/ubuntu/dockbuddy/work/models/_common/test/data)
              MODEL_ROOT  = 本模型权重/资源目录(/home/ubuntu/dockbuddy/models/modeller)
              TEST_DATA   = 本模型自带数据目录(/home/ubuntu/dockbuddy/work/models/modeller/test/data)
  - 输出: **最后一行**打印单行 JSON, 形如
              {"scores": {...}}                      成功
              {"error": "ModellerError: ..."}        失败
    调度器取最后一行解析, 与 test/baseline.json 比对判回归。
  - 本脚本只依赖本目录 + COMMON_DATA + MODEL_ROOT, 不依赖其他模型的内部路径。

Modeller 是**同源建模工具**而非打分模型, 故 scores 装的是「环境可用性计数」而非 ΔΔG:
  import_ok    1 = `import modeller` 成功(conda 包就位)
  environ_ok   1 = `Environ()` 构造成功 —— 这是 license key 的**校验点**,
                   key 无效会直接抛 ModellerError
  modlib_libs  成功读入的 modlib 力场库文件数(拓扑 + 参数 = 2), 证明 conda 包里
               约 30MB 的 modlib 数据文件完整就位, 而不是只有 python 壳

未做「真实 automodel 建模」验证: 需要模板 PDB + PIR 对齐输入且耗时分钟级, 与
smoke 定位(秒级验环境)不符; 真实链路在 pipeline 侧由
components/stability.py stability_modeller() → external_tools.modeller_model() 覆盖。
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/modeller")
DATA = os.environ.get("TEST_DATA", "/home/ubuntu/dockbuddy/work/models/modeller/test/data")
# REPO = 本模型 model.json 的 repo.dest;  REPOS = extra_repos 声明的 {别名: 路径}
REPO = os.environ.get("REPO_DIR", "")
REPOS = json.loads(os.environ.get("REPO_DIRS", "{}") or "{}")


def run():
    # 1) 包就位
    import modeller
    # 2) license key 校验点 + modlib 数据文件就位(拓扑库 + 参数库)
    env = modeller.Environ()
    libs = 0
    for f in ("${LIB}/top_heav.lib", "${LIB}/par.lib"):
        if f.endswith(".lib") and "top" in f:
            env.libs.topology.read(file=f)
        else:
            env.libs.parameters.read(file=f)
        libs += 1
    return {
        "import_ok": 1,
        "environ_ok": 1,
        "modlib_libs": libs,
        "version": str(getattr(modeller, "__version__", "") or ""),
    }


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
