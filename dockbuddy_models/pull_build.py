#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dockbuddy_models/pull_build.py —— 实例端: 从 COS **内网**下载并解包(替代 sftp 传大文件)
===================================================================================
与 deploy/stage_to_cos.py 配对: 本机打包上传 COS(公网) → 本脚本在实例上从 COS 内网
下载(0 元流量)并解包到 /home/ubuntu(即 tar 包内的 home/ubuntu/... 前缀解包到 /)。

sftp 只留几个 KB 级小脚本, 大文件(pipeline 代码 / sourcecode 源码 / 测试数据 /
Miniconda 安装包)全走 COS, 绕开跨公网 sftp 抖动(EOFError/10054)。

用法(实例内, ubuntu 用户, 无需 root):
  python3 /home/ubuntu/pull_build.py                 # 全部(缺省)
  python3 /home/ubuntu/pull_build.py pipeline sourcecode  # 只拉指定 stage
"""
import hashlib
import json
import os
import sys
import tarfile

# 实例端路径常量: 从上传的 dcommon_paths.py 读(与 dcommon/paths.py 单一事实源同步)。
# 本脚本被 sftp 上传到 $HOME/ 下, 用 __file__ 推断 HOME 作 sys.path, 不硬编码路径。
_HOME = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOME)
try:
    from dcommon_paths import HOME, ARC_HOME, ARC_HOME_FIRST, HOME_MODELS  # noqa: E402
except ImportError:  # 兜底(极端: paths.py 未上传, 按脚本位置推断 HOME)
    HOME = _HOME
    ARC_HOME = HOME.lstrip("/")
    ARC_HOME_FIRST = ARC_HOME.split("/")[0]
    HOME_MODELS = f"{HOME}/models"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# COS 下载走 dcommon_cos(→cloud_exec.CosClient, 纯标准库流式), 无需 qcloud_cos SDK。
# dcommon_cos 已自含 CODE_ROOT 注入(work/cloud_exec), import 即可。
from dcommon_cos import pull_file, head_object  # noqa: E402

# tar.gz: 解包到 /(内部 arcname 已带 home/ubuntu/... 前缀)
TARS = {
    "pipeline": "build/pipeline.tar.gz",
    "sourcecode": "build/sourcecode.tar.gz",   # 制镜像路径
    "tests": "build/tests.tar.gz",
}
# 单文件: key → 目标路径
SINGLE = {
    "miniconda": ("build/miniconda.sh", f"{HOME_MODELS}/Miniconda3-latest-Linux-x86_64.sh"),
}


def _safe_extract(tf: tarfile.TarFile, dest: str) -> None:
    """解包, 只接受 {ARC_HOME}/ 前缀成员(防路径穿越; 双保险)。"""
    members = [m for m in tf.getmembers()
               if m.name == ARC_HOME_FIRST or m.name.startswith(ARC_HOME + "/")]
    tf.extractall(dest, members=members)


def _download_tar(key: str, expect_sha256: str = "") -> None:
    if head_object(key, internal=True) < 0:
        print(f"[pull] COS 无对象, 跳过: {key}", flush=True)
        return
    local = "/tmp/" + os.path.basename(key)
    pull_file(key, local, internal=True)
    # sha256 校验(manifest 传来, 防传输损坏/静默错文件; 不一致重拉一次)。
    # ⚠️ manifest 的 sha256 字段是**截断前缀**(16 字符, 与 pack.py 同口径), 而本地算的是
    # 完整 64 字符 —— 直接用 != 比较会永远失败(2026-10-24 部署暴露: src 单元全部
    # 校验失败回退 sftp)。改为**前缀匹配**: 完整值以期望前缀开头即视为一致。
    if expect_sha256:
        actual = _sha256_file(local)
        if not actual.startswith(expect_sha256):
            print(f"[pull] sha256 不一致 {key}: 期望 {expect_sha256[:12]}..., "
                  f"实际 {actual[:12]}..., 重拉一次", flush=True)
            # 先删旧文件再重拉: dcommon_cos.pull_file 对已存在(≥1字节)文件幂等跳过,
            # 不删则"重拉"实际不重下(2026-10-26 部署暴露: test-foldx/test-gnina 因
            # /tmp 旧缓存 sha256 校验失败重拉无效)。
            if os.path.isfile(local):
                os.remove(local)
            pull_file(key, local, internal=True)
            actual = _sha256_file(local)
            if not actual.startswith(expect_sha256):
                raise RuntimeError(f"sha256 校验失败 {key}(重拉后仍不一致)")
    with tarfile.open(local, "r:gz") as tf:
        _safe_extract(tf, "/")
    os.remove(local)
    print(f"[pull] 解包 {key} 完成", flush=True)


def _download_single(key: str, dest: str) -> None:
    if head_object(key, internal=True) < 0:
        print(f"[pull] COS 无对象, 跳过: {key}", flush=True)
        return
    pull_file(key, dest, internal=True)


def main() -> None:
    args = sys.argv[1:]
    # units 子命令: 按需拉部署单元(pack.py 产出的 src-<m>/tool-<t>/extra-*/shared-*),
    # 解包到 /(arcname 已带 home/ubuntu/dockbuddy/... 前缀, 落位即 repo.dest/工具目录)。
    # 这是「源码作为模型资源」的拉取侧: 每个模型一个 src-<m> 单元。
    if args and args[0] == "units":
        # 支持 --sha256 '{"src-geostab": "<sha>", ...}' 校验(本机 manifest 传来)
        expect = {}
        uids = args[1:]
        if "--sha256" in args:
            i = args.index("--sha256")
            expect = json.loads(args[i + 1])
            uids = [a for a in args[1:] if a != "--sha256" and a != args[i + 1]]
        # per-unit 隔离: 单个单元失败不中断其余(2026-10-24 部署暴露: src-venusrem sha256
        # 失败 raise → 整个循环中断, 排在后面的 test-ddgun/test-esm2_hf 被连带牺牲)。
        # 失败记录 + 继续, 最后非 0 退出让调用方感知(已成功的单元保留, 不再全链中断)。
        failed = []
        for uid in uids:
            try:
                _download_tar(f"units/{uid}.tar.gz", expect.get(uid, ""))
            except Exception as e:  # noqa: BLE001
                print(f"[pull] {uid} 失败: {type(e).__name__}: {e}", flush=True)
                failed.append(uid)
        if failed:
            print(f"[pull] 失败 {len(failed)} 个单元: {failed}", flush=True)
            sys.exit(1)
        print("[pull] units 完成", flush=True)
        return
    stages = args or (list(TARS) + list(SINGLE))
    for s in stages:
        if s in TARS:
            _download_tar(TARS[s])
        elif s in SINGLE:
            _download_single(*SINGLE[s])
        else:
            print(f"[pull] 未知 stage(忽略): {s}", flush=True)
    print("[pull] 完成", flush=True)


if __name__ == "__main__":
    main()
