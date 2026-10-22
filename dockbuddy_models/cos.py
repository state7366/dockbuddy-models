# -*- coding: utf-8 -*-
"""cos.py —— COS 对象存储客户端(封装 qcloud_cos, 支持内网/公网 endpoint)。

铁律(与 DockBuddy 同款): 云实例访问 COS 必须走内网 endpoint(cos.<region>.tencentcos.cn,
流量 0 元); 本机/无内网环境走公网。endpoint 由 CosConfig 决定。
qcloud_cos 懒加载 —— 只有真正下载时才 import(纯查询用法无需安装)。
"""
from __future__ import annotations

import os
from typing import Optional

from .config import CosConfig


class CosClient:
    def __init__(self, cfg: CosConfig):
        # 凭证懒加载: 构造不强制要凭证(纯查询/注册/路径用法零凭证依赖),
        # 真正下载时才检查。
        self.cfg = cfg.resolve_credentials()
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            if not self.cfg.secret_id or not self.cfg.secret_key:
                raise RuntimeError(
                    "缺少 COS 凭证: 请设 DOCKBUDDY_MODELS_SECRET_ID/KEY, "
                    "或 ~/.tccli/default.credential, 或显式传入 secret_id/secret_key")
            from qcloud_cos import CosConfig as QCosConfig
            from qcloud_cos import CosS3Client
            kw = dict(Region=self.cfg.region, SecretId=self.cfg.secret_id,
                      SecretKey=self.cfg.secret_key, Scheme=self.cfg.scheme)
            if self.cfg.endpoint:
                kw["Endpoint"] = self.cfg.endpoint
            self._client = CosS3Client(QCosConfig(**kw))
        return self._client

    def download(self, key: str, dest: str, min_bytes: int = 1) -> bool:
        """下载对象到 dest; 已存在且 >=min_bytes 跳过(幂等), 返回是否真正下载。"""
        if os.path.isfile(dest) and os.path.getsize(dest) >= min_bytes:
            return False
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        self._ensure_client().download_file(
            Bucket=self.cfg.bucket, Key=key, DestFilePath=dest)
        return True

    def head_size(self, key: str) -> int:
        """查对象字节数; 不存在返回 -1。"""
        try:
            r = self._ensure_client().head_object(Bucket=self.cfg.bucket, Key=key)
            return int(r.get("Content-Length", 0) or 0)
        except Exception:  # noqa: BLE001
            return -1

    def head_etag(self, key: str) -> str:
        """查 ETag(去引号); 不存在返回 ''。"""
        try:
            r = self._ensure_client().head_object(Bucket=self.cfg.bucket, Key=key)
            return (r.get("ETag", "") or "").strip('"')
        except Exception:  # noqa: BLE001
            return ""

    def upload(self, key: str, local_path: str) -> None:
        """上传本地文件到 COS。"""
        self._ensure_client().upload_file(
            Bucket=self.cfg.bucket, Key=key, LocalFilePath=local_path)
