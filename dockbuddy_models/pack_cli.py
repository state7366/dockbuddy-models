#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tools/deploy/pack.py —— 本地打包全部/指定部署单元 + 自检 + manifest(不联网)
===================================================================================
(自 deploy/stage/pack.py 迁移) 扫 models/*/model.json → 按约定解析单元 → 逐个打包
到 tools/deploy/build/units/<id>.tar.gz → 自检 → 写 manifest。**不上传**(上传是
push.py), 本命令无网络依赖, 可反复跑。

用法:
  python -m tools.deploy.pack --list
  python -m tools.deploy.pack --models geostab,esm2
  python -m tools.deploy.pack --all
"""
from __future__ import annotations

import argparse
import json
import os

from . import pack as U


def _fmt(n: int) -> str:
    if n >= 1 << 30:
        return f"{n / (1 << 30):.2f}G"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f}M"
    return f"{n / (1 << 10):.0f}K"


def cmd_list(a) -> int:
    units = U.resolve_units(a.models or None)
    print(f"{'单元':<22}{'类':<7}{'模型':<14}{'COS key':<34}说明")
    print("-" * 100)
    for u in units:
        models = ",".join(u.models)
        note = u.notes or ("含 patches 同包" if u.apply else "")
        print(f"{u.id:<22}{u.kind:<7}{models:<14}{u.cos_key:<34}{note}")
    print(f"\n共 {len(units)} 个单元; 权重 {sum(len(v) for v in U.weights_manifest(a.models or None).values())} 条声明(走 COS 权重通道, 不打包)")
    return 0


def _load_prev_manifest() -> dict:
    """上次 pack 的完整 manifest(含 units/weights; 缺失/损坏返回 {})。"""
    p = U.BUILD / "manifest.json"
    if not p.is_file():
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def cmd_pack(a) -> int:
    names = a.models or None
    units = U.resolve_units(names)
    if not units:
        print("[pack] 无可打包单元")
        return 0
    out_dir = U.BUILD / "units"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[pack] {len(units)} 个单元 → {out_dir}")

    # 增量打包(建议3): 对比上次 manifest 的 content_sha, 只重打内容变了的单元。
    # --all 全量重打 20 个单元需 8 分钟(PeaZip 压缩 1.3GB), 其中 gnina 820M /
    # miniconda 198M 等几乎不变 —— 按 content_sha 跳过未变单元, 通常秒级收尾。
    prev_full = _load_prev_manifest()
    prev = prev_full.get("units", {})
    packed = {}
    skipped = 0
    for u in units:
        csha = U.content_sha(u)
        tar_path = out_dir / f"{u.id}.tar.gz"
        prev_meta = prev.get(u.id) or {}
        if (not a.force and prev_meta.get("content_sha") == csha
                and tar_path.is_file()):
            packed[u.id] = prev_meta   # 复用上次条目(sha256/size 仍有效, tar 未变)
            skipped += 1
            print(f"  [skip] {u.id:<22} 内容未变, 复用上次打包", flush=True)
            continue
        meta = U.pack_unit(u, out_dir, content_sha_value=csha)
        packed[u.id] = meta
        print(f"  [pack] {u.id:<22} {_fmt(meta['size']):>8}  {meta['files']:>5} 文件"
              f"  [{meta['backend']}]{'  (含 patches)' if u.apply else ''}", flush=True)

    if skipped:
        print(f"[pack] 跳过 {skipped} 个未变单元(用 --force 强制全量重打)")

    # 自检
    errors = U.selfcheck(units, packed)
    errors += U.check_weights_declared(names)
    warns = U.patch_warnings(units)
    for w in warns:
        print(f"  [warn] {w}")
    if errors:
        print(f"\n[pack] ❌ 自检失败 {len(errors)} 项:")
        for e in errors:
            print("   -", e)
        return 3

    # manifest —— **合并**上次条目, 而非整表覆盖(单模型/增量打包时不丢其他单元)。
    # 2026-10-16 踩坑: 旧实现 manifest["units"]=packed, `--models geostab` 会把其余 19 个
    # 单元条目从 manifest 抹掉 → 之后 pull_repos 读 manifest 只看到 geostab, 其余 src 单元
    # 全部静默不拉。合并口径: 上次条目中产物仍在磁盘的保留, 本次 packed 覆盖/新增。
    U.BUILD.mkdir(parents=True, exist_ok=True)
    merged_units = {uid: meta for uid, meta in prev.items()
                    if (out_dir / f"{uid}.tar.gz").is_file()}
    merged_units.update(packed)
    # weights 同样合并(上次 manifest 里未重打模型的 weights 保留; 本次覆盖)
    merged_weights = dict(prev_full.get("weights", {}) or {})
    merged_weights.update(U.weights_manifest(names))
    manifest = {"version": 2, "arc_root": U.ARC_ROOT,
                "units": merged_units, "weights": merged_weights}
    with open(U.BUILD / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    total = sum(m["size"] for m in merged_units.values())
    print(f"\n[pack] ✅ 自检全过; 本次 {len(packed)} 单元, manifest 共 {len(merged_units)} 单元 / {_fmt(total)}")
    print(f"[pack] manifest → {U.BUILD / 'manifest.json'}"
          f"(units {len(merged_units)}, weights "
          f"{sum(len(v) for v in merged_weights.values())} 条)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="本地打包部署单元 + 自检 + manifest(不联网)")
    ap.add_argument("--list", action="store_true", help="只列单元不打包")
    ap.add_argument("--all", action="store_true", help="全部模型(默认)")
    ap.add_argument("--models", default="", help="逗号分隔模型名(缺省=全部)")
    ap.add_argument("--force", action="store_true",
                    help="强制全量重打(默认按 content_sha 增量跳过未变单元)")
    a = ap.parse_args()
    a.models = [m.strip() for m in a.models.split(",") if m.strip()] or None
    if a.list:
        return cmd_list(a)
    return cmd_pack(a)


if __name__ == "__main__":
    raise SystemExit(main())
