# -*- coding: utf-8 -*-
"""dockbuddy_models —— 模型资产唯一归属(注册表 + 下载 + 发布，与 DockBuddy 解耦)。

模型声明单一事实源 = per-model model.json 目录(models_dir)，运行时派生 assets:
    from dockbuddy_models import ModelHub
    hub = ModelHub(models_dir="/path/to/models")   # 读 <models_dir>/*/model.json
    hub.download("esm2")                            # 下权重(assets 由部署字段派生)

提供:
  - 模型注册表(per-model model.json 加载 / 运行时扩充 / assets 派生)
  - 多类型资产下载(权重/源码/工具, 幂等, 校验, 解压, 锁定)
  - 模型权重下载/上传业务(weights.load_models/pull_models/push_models)
  - 发布侧(部署单元打包 pack / 推送 push)
  - 实例端部署路径常量(deploy_paths, HOME 一处派生)
  - 来源抽象(COS / URL / HF / git)
  - 路径配置(资源总根 / 权重根 / 源码根 / 工具根 / 缓存)
"""
from . import deploy_paths
from .cache import CacheStore
from .config import Config, CosConfig
from .cos import CosClient
from .download import Downloader
from .hub import ModelHub
from .registry import Registry, assets_from_spec, load_models_dir
from .sources import AssetSource, extract_archive, sha256_file, verify_sha256
from .weights import load_models, pull_models, push_models

__version__ = "0.5.0"

__all__ = [
    "ModelHub", "Config", "CosConfig", "Registry",
    "CosClient", "Downloader", "CacheStore",
    "AssetSource", "extract_archive", "sha256_file", "verify_sha256",
    "assets_from_spec", "load_models_dir",
    "load_models", "pull_models", "push_models", "deploy_paths",
    "__version__",
]
