# -*- coding: utf-8 -*-
"""hub.py —— ModelHub: 模型资源的统一入口(注册表 + 下载 + 缓存 + 锁定 + 路径)。

把 Config / Registry / CosClient / Downloader / CacheStore 组合成一个对象,
对外提供单一 API。与 DockBuddy 项目完全解耦。

示例:
    from dockbuddy_models import ModelHub, CosConfig
    hub = ModelHub(models="/path/to/models.json",        # 模型数据配置(外部传入, 库壳子不含数据)
                   root="/data/dockbuddy",                # 资源总根
                   cos=CosConfig(endpoint="cos.ap-shanghai.tencentcos.cn"))  # 内网 0 元
    hub.list_models()           # 列出所有模型
    hub.download("saprot")      # 下载某模型全部资产(权重+源码)
    hub.download("esm2", kinds=["weights"])   # 只下权重
    hub.download_all()          # 下载全部 available
    hub.ensure("foldx")         # 幂等确保就位
    hub.register({...})         # 扩充新模型
    hub.lock()                  # 读 lockfile(可复现)
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from . import paths
from .cache import CacheStore
from .config import Config, CosConfig
from .cos import CosClient
from .download import Downloader
from .registry import Registry, load_models_dir


class ModelHub:
    def __init__(self,
                 models: Optional[str] = None,
                 models_dir: Optional[str] = None,
                 registry: Optional[Registry] = None,
                 root: Optional[str] = None,
                 models_root: Optional[str] = None,
                 repos_root: Optional[str] = None,
                 tools_root: Optional[str] = None,
                 cache_dir: Optional[str] = None,
                 cos: Optional[CosConfig] = None):
        base = Config.from_env()
        self.config = Config(
            root=root or base.root,
            models_root=models_root or base.models_root,
            repos_root=repos_root or base.repos_root,
            tools_root=tools_root or base.tools_root,
            cache_dir=cache_dir or base.cache_dir,
            cos=cos or base.cos,
        ).resolve().ensure_dirs()
        # 注册表(库壳子不含数据): 显式 registry > models_dir(per-model 单一事实源) >
        # models 路径 > 环境变量 > 空注册表
        if registry is not None:
            self.registry = registry
        elif models_dir:
            self.registry = load_models_dir(models_dir)
        elif models:
            self.registry = Registry.load(models)
        else:
            env_cfg = os.environ.get("DOCKBUDDY_MODELS_CONFIG", "")
            self.registry = Registry.load(env_cfg) if env_cfg else Registry.empty()
        self.cos = CosClient(self.config.cos)
        self.downloader = Downloader(self.config, self.registry, self.cos)
        self.cache = CacheStore(self.config)

    # ---- 注册表 ----
    def get(self, name: str) -> Optional[dict]:
        return self.registry.get(name)

    def assets(self, name: str) -> Dict:
        return self.registry.assets(name)

    def weights(self, name: str) -> list:
        return self.registry.weights(name)

    def list_models(self, only_available: bool = False) -> List[str]:
        return self.registry.available() if only_available else self.registry.names()

    def available(self) -> List[str]:
        return self.registry.available()

    def register(self, entry: dict, overwrite: bool = False) -> "ModelHub":
        self.registry.register(entry, overwrite=overwrite)
        return self

    def load_registry(self, path: str) -> "ModelHub":
        self.registry.merge(Registry.load(path), overwrite=True)
        return self

    # ---- 下载 ----
    def download(self, name: str, kinds: Optional[List[str]] = None, force: bool = False) -> Dict:
        return self.downloader.download(name, kinds=kinds, force=force)

    def download_all(self, names: Optional[List[str]] = None, kinds: Optional[List[str]] = None,
                     force: bool = False) -> Dict[str, Dict]:
        return self.downloader.download_all(names, kinds=kinds, force=force)

    def ensure(self, name: str, kinds: Optional[List[str]] = None) -> bool:
        return self.downloader.ensure(name, kinds=kinds)

    def lock(self) -> Dict:
        return self.downloader.lock()

    # ---- 缓存 ----
    def cached_models(self) -> List[str]:
        return self.cache.cached_models()

    def total_size(self) -> int:
        return self.cache.total_size()

    def clear_cache(self, model: Optional[str] = None) -> int:
        return self.cache.clear(model)

    # ---- 路径 ----
    def weight_path(self, name: str, dest: str) -> str:
        return paths.asset_path(self.config, "weights", dest)

    def source_path(self, name: str, dest: str) -> str:
        return paths.asset_path(self.config, "source", dest)

    def tool_path(self, rel: str) -> str:
        return paths.tool_path(self.config, rel)

    def model_dir(self, name: str) -> str:
        return paths.model_dir(self.config, name)

    def resolve_tool(self, rel: str) -> Optional[str]:
        return paths.resolve_tool(self.config, rel)

    # ---- 预计下载量 ----
    def model_size(self, name: str) -> int:
        """某模型已缓存总字节数。"""
        return self.cache.model_size(name)
