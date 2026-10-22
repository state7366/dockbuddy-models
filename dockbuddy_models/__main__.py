# -*- coding: utf-8 -*-
"""__main__.py —— 命令行入口: python -m dockbuddy_models 或 dockbuddy-models。

子命令:
  list [--available]            列出模型
  download [<model>|--all]      下载(默认全部资产类型)
  info <model>                  查看模型元数据
  path <model> [--kind weights] 打印资产绝对路径
  size <model>                  已缓存占用
  ensure <model>                幂等确保就位
  lock                          打印 lockfile
全局参数: --root / --models-root / --repos-root / --tools-root / --cache-dir
"""
from __future__ import annotations

import argparse
import json
import sys

from .hub import ModelHub


def _hub(args) -> ModelHub:
    return ModelHub(models=args.models or None, root=args.root,
                    models_root=args.models_root, repos_root=args.repos_root,
                    tools_root=args.tools_root, cache_dir=args.cache_dir)


def _kinds(s: str):
    return [x.strip() for x in s.split(",") if x.strip()] if s else None


def cmd_list(args, hub):
    names = hub.available() if args.available else hub.list_models()
    for n in names:
        e = hub.get(n)
        print(f"{n}\t{e.get('device_req','any')}\t{e.get('status','')}")
    return 0


def cmd_download(args, hub):
    if args.all:
        out = hub.download_all(kinds=_kinds(args.kinds), force=args.force)
        for n, r in out.items():
            print(f"{n}: {r}")
    else:
        if not args.model:
            print("download 需要 <model> 或 --all", file=sys.stderr)
            return 2
        r = hub.download(args.model, kinds=_kinds(args.kinds), force=args.force)
        print(r)
    return 0


def cmd_info(args, hub):
    e = hub.get(args.model)
    if e is None:
        print(f"未注册: {args.model}", file=sys.stderr)
        return 2
    print(json.dumps(e, ensure_ascii=False, indent=2))
    return 0


def cmd_path(args, hub):
    from . import paths
    assets = hub.assets(args.model)
    kind = args.kind or "weights"
    for spec in assets.get(kind, []):
        print(paths.asset_path(hub.config, kind, spec["dest"]))
    return 0


def cmd_size(args, hub):
    print(hub.model_size(args.model))
    return 0


def cmd_ensure(args, hub):
    ok = hub.ensure(args.model)
    print("ok" if ok else "fail")
    return 0 if ok else 1


def cmd_lock(args, hub):
    print(json.dumps(hub.lock(), ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dockbuddy-models", description="打分模型资源管理")
    ap.add_argument("--models", default="", help="模型数据配置文件路径(库壳子不含数据, 须显式传入)")
    ap.add_argument("--root", default="")
    ap.add_argument("--models-root", default="")
    ap.add_argument("--repos-root", default="")
    ap.add_argument("--tools-root", default="")
    ap.add_argument("--cache-dir", default="")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("list")
    p.add_argument("--available", action="store_true")

    p = sub.add_parser("download")
    p.add_argument("model", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--kinds", default="", help="weights,source,tool")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("info")
    p.add_argument("model")

    p = sub.add_parser("path")
    p.add_argument("model")
    p.add_argument("--kind", default="weights")

    p = sub.add_parser("size")
    p.add_argument("model")

    p = sub.add_parser("ensure")
    p.add_argument("model")

    sub.add_parser("lock")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0
    hub = _hub(args)
    return {
        "list": cmd_list, "download": cmd_download, "info": cmd_info,
        "path": cmd_path, "size": cmd_size, "ensure": cmd_ensure, "lock": cmd_lock,
    }[args.cmd](args, hub)


if __name__ == "__main__":
    raise SystemExit(main())
