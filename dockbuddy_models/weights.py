# -*- coding: utf-8 -*-
"""dockbuddy_models/weights.py —— 模型权重下载/上传业务(读 model.json, 单一事实源)。

分层(高内聚低耦合):
  - 通用 COS 对象操作 → cloud_exec.CosClient(纯标准库 + qcloud_cos multipart 懒加载)。
  - 模型权重业务(load_models/pull_models/push_models, 读 per-model model.json) → 本模块。

内网铁律: 云实例访问 COS 必须走内网 endpoint(cos.<region>.tencentcos.cn, 流量 0 元),
严禁公网。本模块内网 client 强制内网 endpoint + http。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .deploy_paths import MODELS_ROOT as _INSTANCE_MODELS_ROOT, abs_dock as _abs_dock

BUCKET = "dockbuddy-models-sh-1252707802"
REGION = "ap-shanghai"
ENDPOINT = "cos.ap-shanghai.tencentcos.cn"
SCHEME = "http"

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(os.path.dirname(_HERE), "models")   # dockbuddy-models/models


def _cos_client(internal: bool = True):
    """COS client。internal=True 内网 endpoint(云实例 0 元); False 公网(本机上传)。"""
    from cloud_exec import CosClient
    if internal:
        return CosClient(BUCKET, endpoint=ENDPOINT, scheme=SCHEME)
    return CosClient(BUCKET)


def load_models(models_root: str = _MODELS_DIR) -> Dict:
    """扫描 <models_root>/*/model.json, 返回 {models: {<目录名>: spec}, bucket, region...}。"""
    models = {}
    if os.path.isdir(models_root):
        for d in sorted(os.listdir(models_root)):
            p = os.path.join(models_root, d, "model.json")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    models[d] = json.load(f)
    return {"bucket": BUCKET, "region": REGION, "endpoint": ENDPOINT,
            "scheme": SCHEME, "models": models}


def _resolve_files(cfg: Dict, names: Optional[List[str]] = None,
                   all_models: bool = False) -> List[Dict]:
    """解析要处理的文件列表 [{cos, dest, model}]。"""
    out = []
    models = cfg.get("models", {})
    for model, spec in models.items():
        if names:
            if model not in names:
                continue
        elif not all_models and not spec.get("default", True):
            continue
        for f in spec.get("weights", []):
            entry = {"model": model, "cos": f["cos"], "dest": f"{model}/{f['dest']}"}
            if f.get("extract"):
                entry["extract"] = f["extract"]
            out.append(entry)
    return out


def _extract_weight(tar_path: str, spec: Dict) -> None:
    """解压 tar.gz 中匹配 glob 的成员到 to 目录(权重 extract 回填, 幂等)。"""
    import fnmatch
    import tarfile
    to = _abs_dock(spec.get("to", ""))
    strip = int(spec.get("strip", 0))
    pat = spec.get("glob", "*")
    if not os.path.isfile(tar_path):
        print(f"[extract] tar 不存在, 跳过: {tar_path}", flush=True)
        return
    done = 0
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not fnmatch.fnmatch(m.name, pat):
                continue
            target = "/".join(m.name.split("/")[strip:])
            dest_path = os.path.join(to, target)
            if os.path.isfile(dest_path) and os.path.getsize(dest_path) == m.size:
                print(f"[extract] 已存在 {target}", flush=True)
                continue
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with tf.extractfile(m) as src, open(dest_path, "wb") as fdst:
                fdst.write(src.read())
            done += 1
            print(f"[extract] {m.name} -> {dest_path}", flush=True)
    print(f"[extract] 完成({done} 个): {tar_path}", flush=True)


def _extract_if_any(f: Dict, dst: str) -> None:
    if f.get("extract"):
        _extract_weight(dst, f["extract"])


def pull_models(names: Optional[List[str]] = None, dest_root: str = _INSTANCE_MODELS_ROOT,
                workers: int = 8, models_root: str = _MODELS_DIR,
                all_models: bool = False) -> int:
    """从 COS 内网下载模型权重(读各模型 model.json), 返回下载文件数。"""
    cfg = load_models(models_root)
    cos = _cos_client(internal=True)
    files = _resolve_files(cfg, names, all_models)
    if not files:
        print("[cos] 无匹配文件(names=%s)" % (names,))
        return 0

    n = 0
    for f in files:
        dst = os.path.join(dest_root, f["dest"])
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            cos_size = cos.head_size(f["cos"])
            etag = cos.head_etag(f["cos"])
            if cos_size == os.path.getsize(dst):
                if etag and "-" not in etag:
                    import hashlib
                    h = hashlib.md5()
                    with open(dst, "rb") as fh:
                        for chunk in iter(lambda: fh.read(1 << 20), b""):
                            h.update(chunk)
                    if etag == h.hexdigest():
                        print(f"[skip] 已存在且 MD5 一致 {f['dest']}", flush=True)
                        _extract_if_any(f, dst)
                        continue
                    print(f"[cos] MD5 不一致, 重新下载 {f['cos']}", flush=True)
                else:
                    print(f"[skip] 已存在(size 一致, multipart 无法直比 MD5) {f['dest']}",
                          flush=True)
                    _extract_if_any(f, dst)
                    continue
            else:
                print(f"[cos] size 不一致({os.path.getsize(dst)} vs {cos_size}), "
                      f"重新下载 {f['cos']}", flush=True)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print(f"[cos] download {f['cos']} -> {f['dest']}", flush=True)
        cos.download_file(f["cos"], dst, min_bytes=1)
        n += 1
        if f.get("extract"):
            _extract_weight(dst, f["extract"])
    print(f"[cos] 完成: {n}/{len(files)} 文件下载", flush=True)
    return n


def push_models(names: Optional[List[str]] = None, local_root: str = "models",
                workers: int = 4, models_root: str = _MODELS_DIR) -> int:
    """上传模型权重到 COS(读各模型 model.json), 返回上传数。本机上传走公网。"""
    cfg = load_models(models_root)
    cos = _cos_client(internal=False)
    files = _resolve_files(cfg, names)

    n = 0
    missing = []
    for f in files:
        lp = os.path.join(local_root, f["dest"])
        if not os.path.exists(lp):
            missing.append(f["dest"])
            continue
        if cos.head_size(f["cos"]) == os.path.getsize(lp):
            print(f"[skip] 已在 COS: {f['cos']}", flush=True)
            continue
        print(f"[upload] {f['cos']} ({os.path.getsize(lp)/1e6:.0f} MB)", flush=True)
        cos.upload_file(f["cos"], lp)
        n += 1
    print(f"[cos] 完成: {n}/{len(files)} 文件上传" + (f"(缺失 {len(missing)})" if missing else ""),
          flush=True)
    if missing:
        print(f"[cos] 缺失(跳过): {missing}", flush=True)
    return n


__all__ = ["load_models", "pull_models", "push_models", "_resolve_files",
           "BUCKET", "REGION", "ENDPOINT", "SCHEME"]
