# -*- coding: utf-8 -*-
"""dockbuddy_models/upload_models.py —— 上传模型权重到 COS(薄入口, 读 model.json)
===================================================================================
(自 tools/deploy/upload_models.py 迁移) 原硬编码 UPLOAD_LIST 已迁入各模型 model.json
(单一事实源)。本文件只做 CLI 参数解析, 实际上传逻辑在 weights.push_models。

用法(本机):
  python -m dockbuddy_models.upload_models --dry-run
  python -m dockbuddy_models.upload_models            # 全部上传
"""
from __future__ import annotations

import argparse
import os

from .pack import MODELS
from .weights import load_models, _resolve_files, push_models


def main():
    ap = argparse.ArgumentParser(description="上传模型权重到 COS(读 model.json)")
    ap.add_argument("--dry-run", action="store_true", help="只打印清单不实际上传")
    ap.add_argument("--models", default="", help="逗号分隔模型名(缺省=全部)")
    a = ap.parse_args()

    names = [x.strip() for x in a.models.split(",") if x.strip()] or None
    if a.dry_run:
        cfg = load_models()
        files = _resolve_files(cfg, names)
        total = 0
        for f in files:
            lp = os.path.join(MODELS, f["dest"])
            if os.path.isfile(lp):
                sz = os.path.getsize(lp)
                total += sz
                print(f"[dry-run] {f['cos']}  ({sz/1e6:.0f} MB)")
        print(f"\n合计 {len(files)} 项, {total/1e9:.2f} GB")
        return
    push_models(names=names, local_root=MODELS)


if __name__ == "__main__":
    main()
