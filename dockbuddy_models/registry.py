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
