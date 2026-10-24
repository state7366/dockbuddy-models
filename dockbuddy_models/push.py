#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dockbuddy_models/push.py —— 上传部署单元到 COS(读 manifest.json, 全部/按 kind)
===================================================================================
(自 tools/deploy/push.py 迁移) pack.py 产出的所有单元由本脚本按 manifest.json 统一推
到 COS units/ 前缀(公网 SDK multipart 分片, 底层 cloud_exec.CosClient)。实例端按需内网拉。

用法:
  python -m dockbuddy_models.push
  python -m dockbuddy_models.push --kind src
  python -m dockbuddy_models.push --only src-geostab src-saprot
  python -m dockbuddy_models.push --list
"""
import argparse
import json
import os

from cloud_exec import CosClient

from .pack import BUILD

BUCKET = "dockbuddy-models-sh-1252707802"
REGION = "ap-shanghai"
ENDPOINT = "cos.ap-shanghai.tencentcos.cn"

HERE = os.path.dirname(os.path.abspath(__file__))   # dockbuddy_models/
UNITS_DIR = os.path.join(BUILD, "units")
MANIFEST = os.path.join(BUILD, "manifest.json")


def _cos(internal: bool = False):
    """本机上传走公网(internal=False)。"""
    if internal:
        return CosClient(BUCKET, endpoint=ENDPOINT, scheme="http")
    return CosClient(BUCKET)


def _load_manifest() -> dict:
    if not os.path.isfile(MANIFEST):
        print(f"[push] 缺 manifest: {MANIFEST}(先跑 pack.py --all)")
        raise SystemExit(2)
    return json.load(open(MANIFEST, encoding="utf-8"))


def _pick(units: dict, kind: str, only: list) -> list:
    """按 kind/--only 过滤单元, 返回 [(id, meta)]。"""
    out = []
    for uid, meta in units.items():
        if only and uid not in only:
            continue
        if kind and meta.get("kind") != kind:
            continue
        out.append((uid, meta))
    return out


def _md5(path: str) -> str:
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _push_one(uid: str, meta: dict) -> int:
    """上传一个单元, 返回实际上传字节数(0=已存在/跳过, -1=失败)。"""
    local = os.path.join(UNITS_DIR, f"{uid}.tar.gz")
    key = meta.get("cos_key") or f"units/{uid}.tar.gz"
    if not os.path.isfile(local):
        print(f"[push] 缺本地包: {local}(先跑 pack.py --all)")
        return -1
    sz = os.path.getsize(local)
    cos = _cos(internal=False)
    remote = cos.head_size(key)
    # 内容级幂等判断(2026-10-17): 原「大小一致即跳过」在本地重新打包后大小**恰好一致**
    # 时会误跳过 → COS 留旧版、manifest 的 sha256 与 COS 实际不一致(实例端 pull_build
    # sha256 校验必失败; catpred src 单元即此)。现改为「大小一致 + COS ETag(单文件 PUT
    # = MD5) 与本地 MD5 一致」才跳过; ETag 含 '-' 是 multipart 复合值无法对比 → 重传。
    if remote == sz:
        etag = cos.head_etag(key)
        if etag and "-" not in etag and etag == _md5(local):
            print(f"[push] 已在 COS(大小+MD5 一致, 跳过): {key} ({sz/1e6:.1f} MB)")
            return 0
        print(f"[push] 大小一致但内容疑变(etag={etag[:16] or '?'}...), 重传 {key}", flush=True)
    print(f"[push] 上传 {key} ({sz/1e6:.1f} MB, 公网 SDK 分片)...", flush=True)
    cos.upload_file(key, local)
    after = cos.head_size(key)
    ok = after == sz
    print(f"[push] {'OK' if ok else 'FAIL'} {key} -> {after/1e6:.1f} MB", flush=True)
    return sz if ok else -1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="", help="只推某类单元(src/tool/test/extra/shared)")
    ap.add_argument("--only", nargs="*", default=[], help="只推指定单元 id")
    ap.add_argument("--list", action="store_true", help="只列将推的单元")
    a = ap.parse_args()

    m = _load_manifest()
    units = m.get("units", {})
    picked = _pick(units, a.kind, a.only)
    if not picked:
        print("[push] 无匹配单元(检查 --kind/--only)")
        return 2
    if a.list:
        for uid, meta in picked:
            print(f"  {uid:<20} kind={meta.get('kind'):<6} {meta.get('size', 0)/1e6:8.1f} MB "
                  f"models={','.join(meta.get('models', [])) or '-'}")
        print(f"共 {len(picked)} 个单元")
        return 0

    total = 0
    failed = 0
    for uid, meta in picked:
        n = _push_one(uid, meta)
        if n < 0:
            failed += 1
        else:
            total += n
    print(f"[push] 完成, 实际上传 {total/1e6:.1f} MB, 失败 {failed} 个")
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
