# -*- coding: utf-8 -*-
"""paths.py —— 路径解析: 权重 / 模型目录 / 本地工具。

所有路径从 Config 派生, 不写死任何绝对路径(与 DockBuddy 解耦)。
weights[].dest 相对 models_root; tools 相对 tools_root。
"""
from __future__ import annotations

import os
from typing import Optional

from .config import Config


def _join(root: str, rel: str) -> str:
    """拼接根与相对路径(空 rel 返回根)。rel 内部正斜杠用 normpath 归一化到本平台分隔符。"""
    rel = (rel or "").replace("\\", "/").strip("/")
    if not rel:
        return root
    return os.path.normpath(os.path.join(root, rel))


def model_dir(config: Config, name: str) -> str:
    """模型权重目录(<models_root>/<name>)。"""
    return _join(config.models_root, name)


def weight_path(config: Config, name: str, dest: str) -> str:
    """权重绝对路径: dest 相对 models_root(全局口径, 支持共享权重如 esm2_hf)。"""
    return _join(config.models_root, dest)


def tool_path(config: Config, rel: str) -> str:
    """本地工具绝对路径: rel 相对 tools_root。"""
    return _join(config.tools_root, rel)


def resolve_tool(config: Config, rel: str) -> Optional[str]:
    """解析工具路径并校验存在; 不存在返回 None。"""
    p = tool_path(config, rel)
    return p if os.path.exists(p) else None


# 资产类型 → 对应配置根字段
_ASSET_ROOT = {"weights": "models_root", "source": "repos_root", "tool": "tools_root"}


def asset_root(config: Config, kind: str) -> str:
    """资产类型对应的根目录(weights→models_root, source→repos_root, tool→tools_root)。"""
    return getattr(config, _ASSET_ROOT.get(kind, "models_root"))


def asset_path(config: Config, kind: str, dest: str) -> str:
    """资产绝对路径: dest 相对该资产类型的根。"""
    return _join(asset_root(config, kind), dest)
