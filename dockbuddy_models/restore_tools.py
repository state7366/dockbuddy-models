#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dockbuddy_models/restore_tools.py —— 实例端: 从 COS 拉工具单元恢复镜像工具
===================================================================================
(自 deploy/restore/restore_tools_on_instance.py 迁移; 实例端脚本, 被 sftp 上传为
$HOME/restore_tools_on_instance.py) 背景: img-lbu0rfer 的 foldx/gnina/caver 被
cleanup bug 删过(models/ glob 只排除 geostab), foldseek/plmc 虽在 /usr/local/bin
但一并重建更完整。本脚本从 COS **内网**拉工具单元, 解包 + 落位 + 软链 + 编译。

2026-10-16 P4 声明化: 不再硬编码 UNITS 清单 + 落位逻辑, 改为读各模型 model.json 的
`tool_install` 声明(kind=binary/unzip/compile/whl)驱动。工具模型(kind=tool)与
evmutation 的 extra_units(tool-plmc/extra-evcouplings)各自声明自己的落位方式,
新增工具只需加 model.json 声明, 不用改本脚本。

实例端用法(经 py_exec 或 ssh 执行; 依赖 model.json 已上传到 /home/ubuntu/models_json):
  python restore_tools_on_instance.py
"""
import json as _json
import os
import subprocess
import sys
import tarfile

# 实例端路径常量: 从上传的 dcommon_paths.py 读(与 dcommon/paths.py 单一事实源同步)。
# 本脚本被 sftp 上传到 $HOME/ 下, 用 __file__ 推断 HOME 作 sys.path, 不硬编码路径。
_HOME = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOME)
try:
    from dcommon_paths import DEPLOY_ROOT, HOME, CONDA_ROOT  # noqa: E402
except ImportError:  # 兜底(极端: paths.py 未上传, 按脚本位置推断 HOME)
    HOME = _HOME
    DEPLOY_ROOT = f"{HOME}/dockbuddy"
    CONDA_ROOT = f"{HOME}/miniconda3"

DEST = DEPLOY_ROOT
MODELS_JSON = f"{HOME}/models_json"


def sh(cmd: str) -> None:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
    tag = "OK " if r.returncode == 0 else "FAIL"
    print(f"[{tag}] {cmd}", flush=True)
    if r.returncode != 0:
        print("   ", (r.stderr or r.stdout or "")[:300], flush=True)
        raise RuntimeError(f"命令失败 rc={r.returncode}: {cmd}")


def discover_tools() -> list:
    """扫描 model.json, 返回 [(单元id, tool_install)]。kind=tool → tool-<m>; extra_units → 其 id。"""
    tools = []
    if not os.path.isdir(MODELS_JSON):
        print(f"[discover] 无 {MODELS_JSON}(model.json 未上传?), 无可恢复工具", flush=True)
        return tools
    for d in sorted(os.listdir(MODELS_JSON)):
        p = os.path.join(MODELS_JSON, d, "model.json")
        if not os.path.isfile(p):
            continue
        spec = _json.load(open(p, encoding="utf-8"))
        if spec.get("kind") == "tool" and spec.get("tool_install"):
            tools.append((f"tool-{d}", spec["tool_install"]))
        for eu in spec.get("extra_units", []):
            if eu.get("tool_install"):
                tools.append((eu.get("id"), eu["tool_install"]))
    return tools


def pull_units() -> None:
    sys.path.insert(0, HOME)
    from cos_util import pull_file  # noqa: E402  (dcommon/cos.py 的实例端副本)
    for uid, _ti in discover_tools():
        local = f"/tmp/{uid}.tar.gz"
        print(f"[pull] units/{uid}.tar.gz (内网)...", flush=True)
        pull_file(f"units/{uid}.tar.gz", local, internal=True)
        with tarfile.open(local, "r:gz") as tf:
            tf.extractall("/")          # arcname 均带 home/ubuntu/ 前缀
        os.remove(local)
        print(f"[pull] {uid} 解包完成", flush=True)


def _gnina_wrapper(bin_link: str) -> None:
    """gnina wrapper: 预编译 gnina 依赖 cudnn9/cudart12/cusparse12..., 系统无 CUDA toolkit
    时从 dockbuddy env 的 nvidia pip 包借 LD_LIBRARY_PATH。真身是 bin_link.bin, wrapper 占 bin_link。"""
    libs = ":".join(
        f"{SP}/nvidia/{d}/lib"
        for d in ("cublas", "cuda_cupti", "cuda_nvrtc", "cuda_runtime",
                  "cudnn", "cufft", "curand", "cusolver", "cusparse",
                  "nccl", "nvjitlink", "nvtx")
        for SP in (f"{CONDA_ROOT}/envs/dockbuddy/lib/python3.10/site-packages",)
        if os.path.isdir(f"{SP}/nvidia/{d}/lib"))
    wrap = "/tmp/gnina_wrapper.sh"
    with open(wrap, "w", encoding="utf-8", newline="\n") as f:
        f.write("#!/bin/bash\n"
                f'export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:{libs}"\n'
                f'exec "{bin_link}.bin" "$@"\n')
    sh(f"sudo install -m 0755 {wrap} {bin_link}")


def _place_binary(ti: dict) -> None:
    """binary: install src→dst(可选) + 软链 + 可选 wrapper/links。"""
    src = f"{DEST}/{ti['src']}"
    dst = ti.get("dst")
    bin_ = ti.get("bin")
    if not os.path.isfile(src):
        print(f"[place] 缺 {src}, 跳过", flush=True)
        return
    if dst:
        os.makedirs(os.path.dirname(f"{DEST}/{dst}"), exist_ok=True)
        sh(f"install -m 0755 {src} {DEST}/{dst}")
        if ti.get("wrapper") == "nvidia_ld" and bin_:
            sh(f"sudo ln -sf {DEST}/{dst} {bin_}.bin")
            _gnina_wrapper(bin_)
        elif bin_:
            sh(f"sudo ln -sf {DEST}/{dst} {bin_}")
    else:
        sh(f"chmod +x {src}")
        if bin_:
            sh(f"sudo ln -sf {src} {bin_}")
        for ln in ti.get("links", []):
            s, d = ln.split(":", 1)
            sh(f"sudo ln -sf {DEST}/{s} {d}")


def _place_unzip(ti: dict) -> None:
    src = f"{DEST}/{ti['src']}"
    dst = f"{DEST}/{ti['dst']}"
    if os.path.isfile(src):
        sh(f"mkdir -p {dst} && unzip -q -o {src} -d {dst}")


def _place_compile(ti: dict) -> None:
    src = f"{DEST}/{ti['src']}"
    if os.path.isdir(src):
        sh(f"cd {src} && make -j4 && sudo cp bin/plmc {ti['bin']}")


def _place_whl(ti: dict) -> None:
    whl = f"{DEST}/{ti['src']}"
    if os.path.isfile(whl):
        sh(f"{CONDA_ROOT}/envs/{ti.get('env', 'dockbuddy')}/bin/pip install -q --no-deps {whl}")


def place_tools() -> None:
    for uid, ti in discover_tools():
        kind = ti.get("kind")
        print(f"[place] {uid} (kind={kind})", flush=True)
        if kind == "binary":
            _place_binary(ti)
        elif kind == "unzip":
            _place_unzip(ti)
        elif kind == "compile":
            _place_compile(ti)
        elif kind == "whl":
            _place_whl(ti)
        else:
            print(f"[place] 未知 kind={kind}, 跳过 {uid}", flush=True)


def link_torch_hub() -> None:
    """2026-10-15 基线扫描坑固化: lfb/esm_if 适配器回退 torch.hub 会从
    dl.fbaipublicfiles.com **公网**拉权重(违反内网铁律)。COS 已拉了全部 esm
    权重到 models/, 把 torch hub 缓存目录软链过去 → 零公网流量直接命中。"""
    hub = os.path.expanduser("~/.cache/torch/hub/checkpoints")
    os.makedirs(hub, exist_ok=True)
    for ms, fn in (("esm2", "esm2_t33_650M_UR50D.pt"), ("esm2", "esm2_t6_8M_UR50D.pt"),
                   ("esm_if/assets", "esm_if1_gvp4_t16_142M_UR50.pt"),
                   ("msa_transformer/assets", "esm_msa1b_t12_100M_UR50S.pt"),
                   ("msa_transformer/assets", "esm_msa1b_t12_100M_UR50S-contact-regression.pt")):
        src = f"{DEST}/models/{ms}/{fn}"
        dst = f"{hub}/{fn}"
        if os.path.isfile(src) and not os.path.exists(dst):
            os.symlink(src, dst)
            print(f"[link] torch hub 缓存: {fn} -> {src}", flush=True)


def verify() -> bool:
    """校验工具在位。返回 True=全部就位, False=有缺失(调用方应显式报错, 不再静默)。

    2026-10-17: 此前只打印 rc 不返回结果, foldx/gnina/caver 缺失时 run_sweep 照样
    进入 setup+两波自测, 直到打分阶段才发现 FAIL, 白白空跑几小时 —— 违反
    「静默失败比崩溃更危险」铁律。现改为返回 bool, main() 据此返回非 0 退出码。
    """
    missing = []
    for b in ("gnina", "foldx", "foldseek", "plmc"):
        r = subprocess.run(f"which {b} && {b} --version 2>&1 | head -1",
                           shell=True, capture_output=True, text=True, timeout=180)
        print(f"[verify] {b}: rc={r.returncode} {(r.stdout or r.stderr).strip()[:80]}",
              flush=True)
        if r.returncode != 0:
            missing.append(b)
    r = subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader",
                       shell=True, capture_output=True, text=True, timeout=60)
    print(f"[verify] GPU: {(r.stdout or r.stderr).strip()}", flush=True)
    jar = f"{DEST}/models/caver/caver.jar"
    jar_ok = os.path.isfile(jar)
    print(f"[verify] caver.jar: {'在位' if jar_ok else '缺失!'}", flush=True)
    if not jar_ok:
        missing.append("caver.jar")
    if missing:
        print(f"[verify] ❌ 缺失工具: {', '.join(missing)}", flush=True)
        return False
    return True


def main() -> int:
    pull_units()
    place_tools()
    link_torch_hub()
    ok = verify()
    print("[restore] 完成" + ("" if ok else " (有工具缺失)"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
