# -*- coding: utf-8 -*-
"""sources.py —— 资产来源抽象 + 解压 + 校验。

一个资产条目(注册表 JSON 里的 dict)声明「来源 + 落位 + 解压 + 校验」:
  {
    "cos": "hot/esm2/xxx.pt",              # 来源四选一: cos / url / hf / git
    "url": "https://...",
    "hf": "org/repo",  "filename": "x.pt",
    "git": "https://github.com/...",  "rev": "main",
    "dest": "esm2/xxx.pt",                 # 相对对应根(download 层拼路径)
    "extract": {"strip": 4} | {"glob":"*.pt","strip":1,"to":"GeoStab"},
    "sha256": "..."                         # 可选校验
  }

AssetSource.fetch(spec, dest_path) 只做实际下载(幂等/校验在 download 层统一做)。
可选依赖懒加载: huggingface_hub(hf) / git 命令(git) 只在真正用时才 import/调用。
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
import tarfile
from typing import Optional

from .cos import CosClient


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: str, expected: str) -> bool:
    """校验文件 sha256; expected 为空视为通过(未声明不校验)。"""
    if not expected:
        return True
    return sha256_file(path).lower() == expected.lower()


def extract_archive(tar_path: str, dest_root: str, ex) -> None:
    """解压 tar.gz。ex: True/None → 整包 strip 0; dict → {strip, glob, to}。

    strip: 去掉成员 arcname 前 N 层目录; glob: fnmatch 过滤成员; to: 相对 dest_root 的目标子目录。
    """
    if isinstance(ex, bool) or not isinstance(ex, dict):
        ex = {"strip": 0}
    strip = int(ex.get("strip", 0) or 0)
    glob_pat = ex.get("glob", "*")
    to = (ex.get("to") or "").strip("/")
    target_root = os.path.join(dest_root, to) if to else dest_root
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            if glob_pat and glob_pat != "*" and not fnmatch.fnmatch(m.name, glob_pat):
                continue
            rel = "/".join(m.name.split("/")[strip:]) if strip else m.name
            if not rel:
                continue
            dest_path = os.path.join(target_root, rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with tf.extractfile(m) as src, open(dest_path, "wb") as fdst:
                fdst.write(src.read())


class AssetSource:
    """资产来源抽象基类。子类实现 _fetch(spec, dest_path) 与 kind 标识。"""
    kind = ""

    def fetch(self, spec: dict, dest_path: str) -> None:
        raise NotImplementedError

    def supports(self, spec: dict) -> bool:
        return spec.get(self.kind, "") != ""


class CosSource(AssetSource):
    kind = "cos"

    def __init__(self, cos: CosClient):
        self.cos = cos

    def fetch(self, spec: dict, dest_path: str) -> None:
        self.cos.download(spec["cos"], dest_path)


class UrlSource(AssetSource):
    kind = "url"

    def fetch(self, spec: dict, dest_path: str) -> None:
        import urllib.request
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        urllib.request.urlretrieve(spec["url"], dest_path)


class HfSource(AssetSource):
    kind = "hf"

    def fetch(self, spec: dict, dest_path: str) -> None:
        from huggingface_hub import hf_hub_download
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        p = hf_hub_download(repo_id=spec["hf"], filename=spec.get("filename"),
                            revision=spec.get("rev"))
        import shutil
        shutil.copyfile(p, dest_path)


class GitSource(AssetSource):
    kind = "git"

    def fetch(self, spec: dict, dest_path: str) -> None:
        rev = spec.get("rev", "")
        cmd = ["git", "clone", spec["git"], dest_path]
        if rev:
            cmd += ["--branch", rev]
        subprocess.run(cmd, check=True)


def get_source(spec: dict, cos: CosClient) -> Optional[AssetSource]:
    """按 spec 的来源字段路由到对应 Source。"""
    if spec.get("cos"):
        return CosSource(cos)
    if spec.get("url"):
        return UrlSource()
    if spec.get("hf"):
        return HfSource()
    if spec.get("git"):
        return GitSource()
    return None
