#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_registry.py —— 从 DockBuddy 仓库抽取打分模型元数据, 生成独立包注册表 v2。

一次性迁移工具(桥接脚本, 不随包分发)。v2 把单一 `weights` 升级为多类型 `assets`:
  - assets.weights —— 权重(cos/dest/extract/sha256)
  - assets.source  —— 源码(COS src-<单元>.tar.gz, extract 解包到 repos/)
  - assets.tool    —— 工具二进制(暂不自动生成, 留空, 用户可 register 补充)

数据源:
  1. models_registry.py 的 MODELS_REGISTRY —— 运行时元数据 + 权威 weights cos/dest。
  2. deploy/models/<模型>/model.json —— pip/repo/default + weights 的 extract + 未接入模型的权重。

dest 口径: 相对各资产根(weights→models_root, source→repos_root, tool→tools_root)。
"""
import argparse
import importlib.util
import json
import os
from datetime import datetime

DEST_PREFIX = "/home/ubuntu/dockbuddy/models/"   # registry 绝对 weights dest 前缀
REPOS_PREFIX = "repos/"                            # repo.dest 的 repos/ 前缀(去掉得相对 repos_root)

# pullUnits → 相对 repos_root 的源码落位目录(消歧: 复用共享源码的模型)
SOURCE_DEST = {
    "saprot": "SaProt",
    "proteinmpnn": "ProteinMPNN",
    "tranception": "Tranception",
    "catpred": "catpred",
    "geostab": "GeoStab",
}


def load_registry(dockbuddy: str) -> dict:
    path = os.path.join(dockbuddy, "deploy", "n8n", "workflow", "models_registry.py")
    spec = importlib.util.spec_from_file_location("models_registry", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MODELS_REGISTRY


def load_model_json(dockbuddy: str, name: str) -> dict:
    path = os.path.join(dockbuddy, "deploy", "models", name, "model.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rel_dest(abs_dest: str) -> str:
    if abs_dest.startswith(DEST_PREFIX):
        return abs_dest[len(DEST_PREFIX):]
    return abs_dest


def _norm_extract(ex) -> dict:
    """extract 规范化: 统一 dict 形式。to 字段保持相对 root(语义=DockBuddy 的 DEPLOY_ROOT)。"""
    if not isinstance(ex, dict):
        return {"strip": 0}
    return dict(ex)


def build_weights(e: dict, mj: dict) -> list:
    """weights 资产: registry 权威优先; 空则回退 model.json(geostab/catpred); extract 从 model.json 补。"""
    weights = []
    mj_w = {w["cos"]: w for w in mj.get("weights", [])}
    if e.get("weights"):
        for w in e["weights"]:
            item = {"cos": w["cos"], "dest": rel_dest(w["dest"])}
            if w["cos"] in mj_w and mj_w[w["cos"]].get("extract"):
                item["extract"] = _norm_extract(mj_w[w["cos"]]["extract"])
            weights.append(item)
    else:
        for w in mj.get("weights", []):
            item = {"cos": w["cos"], "dest": f"{e.get('model', w['cos'])}/{w['dest']}"}
            if w.get("extract"):
                item["extract"] = _norm_extract(w["extract"])
            weights.append(item)
    return weights


def build_source(e: dict, mj: dict) -> list:
    """source 资产: pullUnits → units/src-<单元>.tar.gz, strip 4 层(home/ubuntu/dockbuddy/repos)解包到 root/repos/<dest>。

    dest 是「解压后的目录名」(如 ProteinMPNN); 下载文件用独立文件名 src-<pu>.tar.gz,
    避免下载文件路径与解压目录路径冲突(否则 repos/ProteinMPNN 既是 tar.gz 又是目录 → FileExistsError)。
    """
    pu = e.get("pullUnits", "") or ""
    if not pu:
        return []
    dest = SOURCE_DEST.get(pu, pu)
    return [{"cos": f"units/src-{pu}.tar.gz", "dest": f"src-{pu}.tar.gz",
             "extract": {"strip": 4, "to": f"repos/{dest}"}}]


def main() -> int:
    ap = argparse.ArgumentParser(description="抽取 DockBuddy 打分模型注册表 v2")
    ap.add_argument("--dockbuddy", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    registry = load_registry(a.dockbuddy)
    models = {}
    for name, e in registry.items():
        mj = load_model_json(a.dockbuddy, name)
        models[name] = {
            "name": name,
            "kind": mj.get("kind", "score"),
            "env": e.get("env", "dockbuddy"),
            "python": mj.get("python"),
            "status": e.get("status", "available"),
            "device_req": e.get("device_req", "any"),
            "requires": e.get("requires", {}),
            "params": e.get("params", []),
            "pip": mj.get("pip"),
            "repo": mj.get("repo"),
            "default": bool(mj.get("default", True)),
            "note": e.get("note", "") or mj.get("notes", ""),
            "assets": {
                "weights": build_weights(e, mj),
                "source": build_source(e, mj),
                "tool": [],   # 工具单元需人工确认, 留空; 用户可 register 补充
            },
        }

    out = {"version": "2.0", "source": "dockbuddy",
           "generated_at": datetime.now().isoformat(timespec="seconds"),
           "models": models}
    d = os.path.dirname(a.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    n_avail = sum(1 for m in models.values() if m["status"] == "available")
    n_src = sum(1 for m in models.values() if m["assets"]["source"])
    print(f"[export] {len(models)} 模型(available={n_avail}, 含源码={n_src}) → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
