# -*- coding: utf-8 -*-
"""download.py —— 资产下载器: 多类型(weights/source/tool) / 幂等 / 校验 / 解压 / 锁定。

幂等: dest 已存在且 >1KB 视为就位跳过(force=True 强制重下)。
校验: spec 声明 sha256 时下载后校验, 不匹配重下一次。
解压: spec 声明 extract 时解压 tar.gz(基准 root)。
锁定: 每次落位把 sha256/size 写进 cache_dir/models.lock(可复现)。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from . import paths
from .cache import CacheStore
from .config import Config
from .cos import CosClient
from .registry import Registry
from .sources import extract_archive, get_source, sha256_file, verify_sha256

MIN_BYTES = 1024
LOCK_VERSION = "1.0"


class Downloader:
    def __init__(self, config: Config, registry: Registry, cos: Optional[CosClient] = None):
        self.config = config.resolve()
        self.registry = registry
        self.cos = cos or CosClient(config.cos)
        self.cache = CacheStore(config)
        self.lock_path = os.path.join(config.cache_dir, "models.lock")

    # ---- 锁文件 ----
    def _load_lock(self) -> Dict:
        if not os.path.isfile(self.lock_path):
            return {"version": LOCK_VERSION, "files": {}}
        try:
            with open(self.lock_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"version": LOCK_VERSION, "files": {}}

    def _save_lock(self, lock: Dict) -> None:
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        with open(self.lock_path, "w", encoding="utf-8") as f:
            json.dump(lock, f, ensure_ascii=False, indent=2)

    def _record_lock(self, name: str, kind: str, spec: dict, dest: str) -> None:
        lock = self._load_lock()
        lock["files"][f"{name}/{kind}/{spec.get('dest','')}"] = {
            "sha256": sha256_file(dest) if os.path.isfile(dest) else "",
            "size": os.path.getsize(dest) if os.path.isfile(dest) else 0,
            "source": spec.get("cos") or spec.get("url") or spec.get("hf") or spec.get("git") or "",
        }
        self._save_lock(lock)

    def lock(self) -> Dict:
        """读当前 lockfile。"""
        return self._load_lock()

    # ---- 单资产下载 ----
    def _fetch_one(self, name: str, kind: str, spec: dict, force: bool) -> str:
        """下载单个资产, 返回状态 downloaded/skipped。"""
        dest = paths.asset_path(self.config, kind, spec["dest"])
        exists = os.path.isfile(dest) and os.path.getsize(dest) >= MIN_BYTES
        if exists and not force:
            status = "skipped"
        else:
            src = get_source(spec, self.cos)
            if src is None:
                raise ValueError(f"资产缺来源(cos/url/hf/git): {spec}")
            src.fetch(spec, dest)
            status = "downloaded"
        # 校验(声明了 sha256 才校验; 不匹配重下一次, 再失败则报错)
        if spec.get("sha256") and not verify_sha256(dest, spec["sha256"]):
            src = get_source(spec, self.cos)
            src.fetch(spec, dest)
            if not verify_sha256(dest, spec["sha256"]):
                raise RuntimeError(f"sha256 校验失败: {spec.get('dest')}")
        # 解压(基准 root)
        if spec.get("extract"):
            extract_archive(dest, self.config.root, spec["extract"])
        # 缓存清单 + lockfile
        self.cache.record(name, f"{kind}/{spec.get('dest','')}",
                          os.path.getsize(dest) if os.path.isfile(dest) else 0)
        self._record_lock(name, kind, spec, dest)
        return status

    # ---- 按模型下载 ----
    def download(self, name: str, kinds: Optional[List[str]] = None,
                 force: bool = False) -> Dict:
        """下载单个模型指定资产类型(kinds=None 拉全部类型), 返回统计。"""
        entry = self.registry.get(name)
        if entry is None:
            raise KeyError(f"未注册模型: {name}")
        assets = entry.get("assets", {})
        if kinds is None:
            kinds = [k for k in ("weights", "source", "tool") if assets.get(k)]
        n_dl = n_skip = n_total = 0
        for kind in kinds:
            for spec in assets.get(kind, []):
                n_total += 1
                st = self._fetch_one(name, kind, spec, force)
                if st == "downloaded":
                    n_dl += 1
                else:
                    n_skip += 1
        return {"model": name, "n_total": n_total,
                "n_downloaded": n_dl, "n_skipped": n_skip}

    def download_all(self, names: Optional[List[str]] = None, kinds: Optional[List[str]] = None,
                     force: bool = False, only_available: bool = True) -> Dict[str, Dict]:
        """批量下载。names=None 拉全部 available。"""
        if names is None:
            names = self.registry.available() if only_available else self.registry.names()
        out = {}
        for n in names:
            if n not in self.registry:
                out[n] = {"model": n, "error": "未注册"}
                continue
            try:
                out[n] = self.download(n, kinds=kinds, force=force)
            except Exception as e:  # noqa: BLE001
                out[n] = {"model": n, "error": f"{type(e).__name__}: {e}"}
        return out

    def ensure(self, name: str, kinds: Optional[List[str]] = None) -> bool:
        """幂等确保资产就位(缺则补下), 全部就位返回 True。"""
        entry = self.registry.get(name)
        if entry is None:
            return False
        assets = entry.get("assets", {})
        if kinds is None:
            kinds = [k for k in ("weights", "source", "tool") if assets.get(k)]
        for kind in kinds:
            for spec in assets.get(kind, []):
                dest = paths.asset_path(self.config, kind, spec["dest"])
                if not (os.path.isfile(dest) and os.path.getsize(dest) >= MIN_BYTES):
                    self._fetch_one(name, kind, spec, force=False)
        return True
