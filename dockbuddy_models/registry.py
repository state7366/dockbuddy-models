# -*- coding: utf-8 -*-
"""registry.py —— 模型注册表(纯壳子): 加载 / 查询 / 扩充。

本库**不内置任何具体模型数据** —— 模型注册表是外部 JSON 配置文件, 使用时显式传入:
  Registry.load("path/to/models.json")   从外部 JSON 加载
  Registry.empty()                        空注册表(壳子无数据时)
  hub.register({...})                     运行时扩充

数据与代码分离: 库只保留逻辑壳子, 模型数据(权重清单/源码单元/依赖)由调用方提供。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

# 模型条目必需字段 + 可选字段(缺省值), 用于 register() 的归一化
_DEFAULTS = {
    "kind": "score",
    "env": "dockbuddy",
    "python": None,
    "status": "available",
    "device_req": "any",
    "requires": {},
    "params": [],
    "pip": None,
    "repo": None,
    "default": True,
    "note": "",
    "assets": {"weights": [], "source": [], "tool": []},
}


@dataclass
class Registry:
    """模型注册表。models: {name: entry}。"""

    models: Dict[str, dict] = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)

    # ---- 加载 ----
    @classmethod
    def load(cls, path: str) -> "Registry":
        """从外部 JSON 文件加载(必须显式传路径)。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        reg = cls(models=data.get("models", {}), meta=data)
        reg.meta.pop("models", None)  # 避免 meta 里冗余 models
        return reg

    @classmethod
    def empty(cls) -> "Registry":
        """空注册表(库壳子无数据时)。"""
        return cls(models={}, meta={})

    # ---- 查询 ----
    def get(self, name: str) -> Optional[dict]:
        return self.models.get(name)

    def assets(self, name: str) -> Dict:
        """某模型的资产清单 {weights:[], source:[], tool:[]}(缺省空)。"""
        return self.models.get(name, {}).get("assets", {"weights": [], "source": [], "tool": []})

    def weights(self, name: str) -> list:
        """向后兼容: 某模型的权重清单。"""
        return self.assets(name).get("weights", [])

    def __getitem__(self, name: str) -> dict:
        if name not in self.models:
            raise KeyError(f"未注册模型: {name}")
        return self.models[name]

    def __contains__(self, name: str) -> bool:
        return name in self.models

    def names(self) -> List[str]:
        return sorted(self.models.keys())

    def available(self, names: Optional[Iterable[str]] = None) -> List[str]:
        """status=available 的模型名; names 给定时取交集。"""
        avail = [n for n, m in self.models.items() if m.get("status") == "available"]
        if names is None:
            return sorted(avail)
        wanted = set(names)
        return [n for n in avail if n in wanted]

    def by_device(self, req: str) -> List[str]:
        """按 device_req 过滤(gpu/cpu/any)。"""
        return [n for n, m in self.models.items() if m.get("device_req") == req]

    # ---- 扩充 ----
    def register(self, entry: dict, overwrite: bool = False) -> "Registry":
        """注册/覆盖一个模型条目。entry 缺省字段用 _DEFAULTS 补齐。

        entry 最小示例: {"name": "mymodel", "weights": [{"cos": "...", "dest": "..."}]}
        """
        name = entry.get("name", "")
        if not name:
            raise ValueError("register() 的 entry 需要 name 字段")
        if name in self.models and not overwrite:
            raise KeyError(f"模型已存在: {name}(覆盖请 overwrite=True)")
        merged = dict(_DEFAULTS)
        merged.update(entry)
        merged["name"] = name
        self.models[name] = merged
        return self

    def merge(self, other: "Registry", overwrite: bool = True) -> "Registry":
        """合并另一个注册表(扩充用)。overwrite=True 时同名覆盖。"""
        for name, entry in other.models.items():
            if name in self.models and not overwrite:
                continue
            self.models[name] = entry
        return self


def assets_from_spec(name: str, spec: dict, models_dir: Optional[str] = None) -> Dict:
    """从 model.json 的部署字段派生 assets(下载视图)，与 pack.py 单元口径对齐。

    - weights: spec.weights[].{cos,dest,extract}，dest 相对模型目录 → 拼 <name>/<dest>。
    - source: 有 sourcecode 目录 → units/src-<name>.tar.gz（pack 产出，strip 4 解包到 repos/）。
    - tool:   tool_install → units/tool-<name>.tar.gz；extra_units → units/<id>.tar.gz。
    这是「部署字段为主，assets 派生」的单一事实源落地：Downloader 不再依赖独立 models.json。
    """
    from pathlib import Path
    assets = {"weights": [], "source": [], "tool": []}
    for w in spec.get("weights") or []:
        item = {"cos": w["cos"], "dest": f"{name}/{w['dest']}"}
        if w.get("extract"):
            item["extract"] = w["extract"]
        assets["weights"].append(item)
    if models_dir and (Path(models_dir) / name / "sourcecode").is_dir():
        assets["source"].append({"cos": f"units/src-{name}.tar.gz",
                                 "dest": f"src-{name}.tar.gz",
                                 "extract": {"strip": 4, "to": "repos"}})
    if spec.get("tool_install"):
        assets["tool"].append({"cos": f"units/tool-{name}.tar.gz",
                               "dest": f"tool-{name}.tar.gz"})
    for ex in spec.get("extra_units") or []:
        uid = ex.get("id") or f"extra-{name}"
        assets["tool"].append({"cos": f"units/{uid}.tar.gz", "dest": f"{uid}.tar.gz"})
    return assets


def load_models_dir(models_dir: str) -> "Registry":
    """从 per-model model.json 目录加载注册表(单一事实源)，assets 运行时派生。

    每个 <models_dir>/<模型>/model.json 一个条目；kind/status/env/python/pip/repo/
    default/device_req 等原样保留，assets 由 assets_from_spec 派生。
    """
    import os as _os
    reg = Registry(models={}, meta={})
    if not _os.path.isdir(models_dir):
        return reg
    for name in sorted(_os.listdir(models_dir)):
        p = _os.path.join(models_dir, name, "model.json")
        if not _os.path.isfile(p):
            continue
        spec = json.load(open(p, encoding="utf-8"))
        entry = dict(_DEFAULTS)
        entry.update(spec)
        entry["name"] = name
        entry["assets"] = assets_from_spec(name, spec, models_dir)
        reg.models[name] = entry
    return reg
