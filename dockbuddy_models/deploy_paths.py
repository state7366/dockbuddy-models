# -*- coding: utf-8 -*-
"""dockbuddy_models/deploy_paths.py —— 实例端部署路径常量(单一事实源)。

所有实例端路径从 HOME 一处派生, 迁移部署根只改 HOME。零依赖(只 import 标准库)。
DockBuddy 实例端部署约定: 资源全放 ubuntu 家目录 /home/ubuntu/dockbuddy。
"""
from __future__ import annotations

import os

# 部署用户家目录 —— 迁移只改这一处(可经 DOCK_DEPLOY_HOME 覆盖)
HOME = os.environ.get("DOCK_DEPLOY_HOME", "/home/ubuntu").rstrip("/")

# conda 安装根
CONDA_ROOT = f"{HOME}/miniconda3"

# 部署根(用户约定: 资源全放 ubuntu 家目录)
DEPLOY_ROOT = f"{HOME}/dockbuddy"
MODELS_ROOT = f"{DEPLOY_ROOT}/models"      # 权重/工具根(软链 /data/models)
CODE_ROOT = f"{DEPLOY_ROOT}/work"          # 代码(pipeline/各模型 test 上传处)
REPOS_ROOT = f"{DEPLOY_ROOT}/repos"        # 第三方源码仓库根

# 制镜像 LOCAL_ASSETS 安装期资源
HOME_MODELS = f"{HOME}/models"             # /home/ubuntu/models(LOCAL_ASSETS, 系统盘)

# 补丁源落位
PATCHES_ROOT = f"{DEPLOY_ROOT}/_patches"

# tar 内 arcname 前缀(无前导斜杠; 与 DEPLOY_ROOT 同源)
ARC_HOME = HOME.lstrip("/")                # home/ubuntu
ARC_HOME_FIRST = ARC_HOME.split("/")[0]    # home(tar 内第一级目录)
ARC_ROOT = f"{ARC_HOME}/dockbuddy"         # home/ubuntu/dockbuddy
PATCHES_ARC = f"{ARC_ROOT}/_patches"


def abs_dock(path: str) -> str:
    """相对 DEPLOY_ROOT 的路径 → 实例端绝对路径(兼容旧绝对路径声明)。"""
    p = (path or "").rstrip("/")
    if not p:
        return ""
    if p.startswith("/"):
        return p
    return f"{DEPLOY_ROOT}/{p}"


__all__ = ["HOME", "CONDA_ROOT", "DEPLOY_ROOT", "MODELS_ROOT", "CODE_ROOT",
           "REPOS_ROOT", "HOME_MODELS", "PATCHES_ROOT", "ARC_HOME",
           "ARC_HOME_FIRST", "ARC_ROOT", "PATCHES_ARC", "abs_dock"]
