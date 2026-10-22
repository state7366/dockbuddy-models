# -*- coding: utf-8 -*-
"""config.py —— 全局配置: 资源总根 / 权重路径 / 源码路径 / 工具路径 / 缓存 / COS。

v2 引入 `root`(资源总根, 语义 = DockBuddy 的 DEPLOY_ROOT) + `repos_root`(源码根)。
weights/source/tool 三类资产各有自己的根:
  - weights → models_root (= root/models)
  - source  → repos_root  (= root/repos)
  - tool    → tools_root  (= root/tools)
优先级: 显式参数 > 环境变量 > 默认值。与 DockBuddy 项目完全解耦。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

ENV_PREFIX = "DOCKBUDDY_MODELS"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"{ENV_PREFIX}_{name}", default)


def _default_cache_root() -> str:
    return str(Path.home() / ".cache" / "dockbuddy_models")


def _load_tccli_cred() -> Dict[str, str]:
    path = Path.home() / ".tccli" / "default.credential"
    if not path.is_file():
        return {}
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        return {"secret_id": cfg.get("secretId", ""), "secret_key": cfg.get("secretKey", "")}
    except (OSError, ValueError):
        return {}


@dataclass
class CosConfig:
    bucket: str = "dockbuddy-models-sh-1252707802"
    region: str = "ap-shanghai"
    endpoint: Optional[str] = None
    scheme: str = "http"
    secret_id: str = ""
    secret_key: str = ""

    def resolve_credentials(self) -> "CosConfig":
        if not self.secret_id:
            self.secret_id = _env("SECRET_ID", os.environ.get("TENCENT_SECRET_ID", ""))
        if not self.secret_key:
            self.secret_key = _env("SECRET_KEY", os.environ.get("TENCENT_SECRET_KEY", ""))
        if not self.secret_id:
            cred = _load_tccli_cred()
            self.secret_id = cred.get("secret_id", "")
            self.secret_key = cred.get("secret_key", "")
        return self


@dataclass
class Config:
    """模型资源全局配置。

    - root:        资源总根(weights/source/tool/cache 的父级)。
    - models_root: 权重下载根(weights[].dest 相对此目录)。
    - repos_root:  源码根(source[].dest 相对此目录)。
    - tools_root:  本地工具根(tool[].dest 相对此目录)。
    - cache_dir:   缓存目录(下载清单 / lockfile)。
    """
    root: str = field(default_factory=_default_cache_root)
    models_root: str = ""
    repos_root: str = ""
    tools_root: str = ""
    cache_dir: str = ""
    cos: CosConfig = field(default_factory=CosConfig)

    @classmethod
    def from_env(cls) -> "Config":
        # 子根默认返回空字符串, 交由 resolve() 从 root 派生 —— 避免"默认值"与"显式值"混淆
        return cls(
            root=_env("ROOT", _default_cache_root()),
            models_root=_env("MODELS_ROOT", ""),
            repos_root=_env("REPOS_ROOT", ""),
            tools_root=_env("TOOLS_ROOT", ""),
            cache_dir=_env("CACHE_DIR", ""),
            cos=CosConfig(
                bucket=_env("COS_BUCKET", "dockbuddy-models-sh-1252707802"),
                region=_env("COS_REGION", "ap-shanghai"),
                endpoint=_env("COS_ENDPOINT", "") or None,
                scheme=_env("COS_SCHEME", "http"),
                secret_id=_env("SECRET_ID", ""),
                secret_key=_env("SECRET_KEY", ""),
            ),
        )

    def resolve(self) -> "Config":
        """派生未显式指定的根(空 → root/<子目录>); models_root 显式时 repos_root 从其父级派生。"""
        if not self.root:
            self.root = _default_cache_root()
        if not self.models_root:
            self.models_root = os.path.join(self.root, "models")
        if not self.repos_root:
            base = os.path.dirname(self.models_root) if self.models_root else self.root
            self.repos_root = os.path.join(base, "repos")
        if not self.tools_root:
            self.tools_root = os.path.join(self.root, "tools")
        if not self.cache_dir:
            self.cache_dir = os.path.join(self.root, "cache")
        return self

    def ensure_dirs(self) -> "Config":
        for d in (self.models_root, self.repos_root, self.tools_root, self.cache_dir):
            if d:
                os.makedirs(d, exist_ok=True)
        return self

    def to_dict(self) -> Dict:
        return asdict(self)
