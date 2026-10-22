# -*- coding: utf-8 -*-
"""dockbuddy_models —— 打分模型资源管理「壳子」(与 DockBuddy 项目解耦)。

本库**不含任何具体模型数据** —— 模型注册表是外部 JSON 配置文件, 使用时显式传入:
    from dockbuddy_models import ModelHub
    hub = ModelHub(models="/path/to/models.json")

提供(纯逻辑壳子):
  - 模型注册表(外部 JSON 加载 / 运行时扩充)
  - 多类型资产下载(权重/源码/工具, 幂等, 校验, 解压, 锁定)
  - 来源抽象(COS / URL / HF / git)
  - 路径配置(资源总根 / 权重根 / 源码根 / 工具根 / 缓存)
"""
from .cache import CacheStore
from .config import Config, CosConfig
from .cos import CosClient
from .download import Downloader
from .hub import ModelHub
from .registry import Registry
from .sources import AssetSource, extract_archive, sha256_file, verify_sha256

__version__ = "0.3.0"

__all__ = [
    "ModelHub", "Config", "CosConfig", "Registry",
    "CosClient", "Downloader", "CacheStore",
    "AssetSource", "extract_archive", "sha256_file", "verify_sha256",
    "__version__",
]
