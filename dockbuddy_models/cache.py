# -*- coding: utf-8 -*-
"""cache.py —— 缓存清单管理(下载历史 / 占用查询 / 清理)。

缓存分两层:
  1. 幂等下载(核心): 权重文件已存在且非空则跳过下载(见 download.py)。
  2. 本模块的清单(cache_dir/download_manifest.json): 记录每个模型各权重文件的
     落位路径/大小/时间, 支撑「已缓存哪些模型 / 占用多大 / 清理」。
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from .config import Config


class CacheStore:
    def __init__(self, config: Config):
        self.config = config
        self.manifest_path = os.path.join(config.cache_dir, "download_manifest.json")

    def _load(self) -> Dict:
        if not os.path.isfile(self.manifest_path):
            return {"models": {}}
        try:
            with open(self.manifest_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"models": {}}

    def record(self, model: str, dest: str, size: int) -> None:
        """记录一次权重文件落位(按模型聚合)。"""
        d = self._load()
        m = d["models"].setdefault(model, {"files": {}})
        m["files"][dest] = {"size": size, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        m["total_size"] = sum(f.get("size", 0) for f in m["files"].values())
        d["models"][model] = m
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

    def cached_models(self) -> List[str]:
        """已缓存(有下载记录)的模型名。"""
        return sorted(self._load()["models"].keys())

    def model_size(self, model: str) -> int:
        """某模型已缓存总字节数。"""
        return self._load()["models"].get(model, {}).get("total_size", 0)

    def total_size(self) -> int:
        """全部缓存总字节数。"""
        return sum(m.get("total_size", 0) for m in self._load()["models"].values())

    def clear(self, model: Optional[str] = None) -> int:
        """清理缓存清单记录(不删文件); model=None 清全部, 返回清理的模型数。"""
        d = self._load()
        if model is None:
            n = len(d["models"])
            d["models"] = {}
        elif model in d["models"]:
            del d["models"][model]
            n = 1
        else:
            n = 0
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        return n
