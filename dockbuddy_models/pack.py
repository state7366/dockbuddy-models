# -*- coding: utf-8 -*-
"""dcommon/unit.py —— 部署单元: model.json → 解析 → 本地打包 → 自检 → manifest
===================================================================================
v2 架构核心(2026-10-15, 设计见 docs/deploy-v2-design.md; 替代 stage_to_cos.py 的
打包职责): 一个模型的自包含物料(sourcecode + patches)打成**一个** COS 单元, 工具
二进制各打一个单元 —— 改一个模型只重传它的单元(如 geostab 补丁变更 → 传 ~6M 的
units/src-geostab.tar.gz, 不再是 1030MB 整包)。

**约定优先**: model.json 不写 unit 声明时按目录约定推断, 只给例外写显式声明
(35 个 model.json 零改动起步; geostab 的 exclude 是第一个显式例外)。

约定:
  - models/<m>/sourcecode/ 存在 → src-<m> 单元(COS: units/src-<m>.tar.gz):
      * sourcecode 只有唯一顶层目录时该目录即仓库根, 其**内容**映射到 repo.dest
        (sftp 平铺造成的 repos/X/X 双层嵌套在打包层消掉, repo_subdir 字段不再需要);
      * 多顶层条目时 sourcecode 内容直接映射到 repo.dest(仓库根=dest);
      * patches/ 若存在则与源码**同包**(arcname home/ubuntu/models/_patches/<m>/), 并生成
        apply 规则(from=/home/ubuntu/models/_patches/<m> → to=repo.dest), 保证应用顺序与原子性;
  - 工具模型(有 assets/、无 sourcecode、无 weights 声明) → tool-<t> 单元:
      * assets/ 下目录条目 X → models/<t>/ 的内容; 文件条目 X → models/X
        (复刻旧 stage_to_cos 的 foldx/gnina/caver/foldseek/plmc 映射, 实例端行为不变);
  - 全局默认排除: .git/ __pycache__/ .pytest_cache/ + .pyc/.pyo
    (实测 6 个 sourcecode 树带 .git 共 283M 死重; 旧 tarball filter 同款排除);
  - weights(model.json 的 weights 声明)**不打包** —— 走既有 COS 权重通道
    (hot/warm/cold 按模型拉取), pack 只生成权重清单 manifest 供实例端 pull 使用;
  - extra_units: model.json 可声明约定之外的附加单元(如 evmutation 的 plmc 编译
    工具树, 本地在 models/evmutation/assets/plmc, 落位 bin/plmc)。

自检(打包后强制执行, 任一失败整体失败):
  1. tar 可读(等价 gzip -t)
  2. arcname 白名单: 只允许 home/ubuntu/ 前缀(防路径穿越)
  3. 跨单元无同 arcname 冲突
  4. patches 与 sourcecode 对应文件内容一致(除 CRLF→LF 规范化)—— 防补丁漂移;
     补丁文件在源码中不存在 → 记 warning(新增型补丁, 合法但列出)
  5. model.json 声明的 weights 本地文件存在性
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# DockBuddy 部署路径约定（tar arcname 前缀 + 实例端落位根）。高内聚：打包发布侧
# 与 DockBuddy 实例端部署根强绑定，故这里收敛为模块级常量，供本包 pack/push 与
# 主仓库 shim 共用。可经环境变量 DOCK_DEPLOY_ROOT 覆盖（缺省 /home/ubuntu/dockbuddy）。
# ---------------------------------------------------------------------------
DEPLOY_ROOT = os.environ.get("DOCK_DEPLOY_ROOT", "/home/ubuntu/dockbuddy").rstrip("/")
_HOME = DEPLOY_ROOT.rsplit("/", 1)[0]           # /home/ubuntu
ARC_HOME = _HOME.lstrip("/")                     # home/ubuntu
ARC_HOME_FIRST = ARC_HOME.split("/")[0]          # home
ARC_ROOT = f"{ARC_HOME}/dockbuddy"               # home/ubuntu/dockbuddy
PATCHES_ROOT = f"{DEPLOY_ROOT}/_patches"
PATCHES_ARC = f"{ARC_ROOT}/_patches"
DOCK_ROOT = DEPLOY_ROOT


def abs_dock(path: str) -> str:
    """相对 DEPLOY_ROOT 的路径 → 实例端绝对路径(兼容旧绝对路径声明)。"""
    p = (path or "").rstrip("/")
    if not p:
        return ""
    if p.startswith("/"):
        return p
    return f"{DEPLOY_ROOT}/{p}"


HERE = Path(__file__).resolve().parent            # dockbuddy_models/ 包目录
PKG_ROOT = HERE.parent                            # dockbuddy-models/
MODELS = Path(os.environ.get("DOCKBUDDY_MODELS_DIR", PKG_ROOT / "models"))
BUILD = Path(os.environ.get("DOCKBUDDY_BUILD_DIR", PKG_ROOT / "build"))

# 实例端路径常量已收敛到本模块(DEPLOY_ROOT 一处派生); 此处 re-export 兼容旧引用:
#   ARC_ROOT  tar 内路径根(解包即落位)
#   DOCK_ROOT 实例端部署根(=/home/ubuntu/dockbuddy)

DEFAULT_EXCLUDE_DIRS = (".git", "__pycache__", ".pytest_cache", ".ipynb_checkpoints")
DEFAULT_EXCLUDE_SUFFIX = (".pyc", ".pyo", ".DS_Store")

# COS 对象 key 前缀(新文件夹, 与旧 build/ 整包时代彻底分手)
UNITS_PREFIX = "units"


@dataclass
class Source:
    """一个打包源: root 的内容映射到 arc_prefix 之下。"""
    root: Path                       # 本地目录(取其内容)
    arc_prefix: str                  # home/ubuntu/dockbuddy/...
    exclude: Tuple[str, ...] = ()    # glob, 相对 root; 命中即排除(目录模式连带子树)


@dataclass
class Unit:
    id: str                          # src-geostab / tool-gnina / extra-plmc
    kind: str                        # src | tool | extra
    cos_key: str                     # units/src-geostab.tar.gz
    sources: List[Source] = field(default_factory=list)
    apply: Optional[dict] = None     # {"from": "_patches/<m>", "to": "repos/<m>"}(实例端, 相对 dockbuddy)
    models: List[str] = field(default_factory=list)   # 来源模型
    notes: str = ""


# ---------------------------------------------------------------- 模型清单
def all_models() -> List[str]:
    """有 model.json 的模型目录(按名排序; _common 等共享目录跳过)。"""
    out = []
    for d in sorted(os.listdir(MODELS)):
        if d.startswith("_"):
            continue
        if (MODELS / d / "model.json").is_file():
            out.append(d)
    return out


def load_spec(name: str) -> dict:
    with open(MODELS / name / "model.json", encoding="utf-8") as f:
        return json.load(f)


def _rel_dock(path: str) -> str:
    """实例端绝对路径 → 相对 dockbuddy 根的相对路径(arcname 用)。"""
    p = path.rstrip("/")
    if p.startswith(DOCK_ROOT + "/"):
        return p[len(DOCK_ROOT) + 1:]
    if p.startswith(DOCK_ROOT):
        return ""
    return p.lstrip("/")


def _excluded(rel: str, patterns: Tuple[str, ...]) -> bool:
    """rel(posix 相对路径)是否命中排除模式。目录模式('data/')连带整棵子树。"""
    parts = rel.split("/")
    for i in range(1, len(parts) + 1):
        prefix = "/".join(parts[:i])
        for pat in patterns:
            if fnmatch.fnmatch(prefix, pat.rstrip("/")):
                return True
    return False


# ---------------------------------------------------------------- 单元解析
def resolve_src_unit(name: str, spec: dict) -> Optional[Unit]:
    """models/<name>/sourcecode/ → src-<name> 单元(含 patches 同包 + apply 规则)。"""
    src = MODELS / name / "sourcecode"
    if not src.is_dir():
        return None
    repo = spec.get("repo") or {}
    # model.json 的 repo.dest 声明为相对 DEPLOY_ROOT 的路径(如 repos/<m>),
    # abs_dock 转成实例端绝对路径(兼容旧绝对路径声明); _rel_dock 再转相对算 arcname。
    dest = abs_dock(repo.get("dest") or f"repos/{name}")
    arc_dest = _rel_dock(dest)

    # 唯一顶层目录 → 该目录即仓库根, 内容映射到 dest(消嵌套); 否则 sourcecode 内容直接映射
    top = [p for p in sorted(src.iterdir())]
    dirs = [p for p in top if p.is_dir()]
    if len(top) == 1 and dirs:
        root = dirs[0]
    else:
        root = src

    unit_decl = spec.get("unit") or {}
    excludes = tuple(DEFAULT_EXCLUDE_DIRS) + tuple(unit_decl.get("exclude") or ())

    u = Unit(id=f"src-{name}", kind="src", cos_key=f"{UNITS_PREFIX}/src-{name}.tar.gz",
             sources=[Source(root=root, arc_prefix=f"{ARC_ROOT}/{arc_dest}", exclude=excludes)],
             models=[name])

    # patches 同包 + apply 规则(落位与制镜像/跑测试两条路径一致: PATCHES_ROOT/<m>)
    patches = MODELS / name / "patches"
    if patches.is_dir() and any(patches.iterdir()):
        u.sources.append(Source(root=patches, arc_prefix=f"{PATCHES_ARC}/{name}"))
        u.apply = {"from": f"{PATCHES_ROOT}/{name}", "to": dest}
        u.notes = "patches 与源码同包; 实例端 apply 后源目录可删"

    # test/ 同包(2026-10-17 B 方案): framework 不再含各模型 test, 改随 src 单元按需拉,
    # 落位 work/models/<m>/test(与 run_model_tests 的 TESTS_ROOT=CODE_ROOT/models 一致)。
    # 扩充模型只重打该模型的 src 单元, framework 永不重打。
    test_dir = MODELS / name / "test"
    if test_dir.is_dir():
        u.sources.append(Source(root=test_dir,
                                arc_prefix=f"{ARC_ROOT}/work/models/{name}/test",
                                exclude=tuple(DEFAULT_EXCLUDE_DIRS)))
    return u


def resolve_test_unit(name: str, spec: dict) -> Optional[Unit]:
    """无 sourcecode 但有 test/ 的模型 → test-<name> 单元(测试脚本+数据+基线)。

    有 sourcecode 的模型 test/ 已随 src 单元打包(resolve_src_unit), 此处只兜住
    「源码不进 COS 单元」的模型(依赖 conda env + 权重: esm1v/esm2/ddgun/lfb/msa_transformer
    等打分模型 + caver/foldseek/foldx/gnina 等工具模型): 它们没有 src 单元, test/ 必须有
    独立载体才能按需拉取(拉取侧 instance._src_unit_ids 认 kind in (src, test))。
    落位 work/models/<name>/test(与 run_model_tests 的 TESTS_ROOT=CODE_ROOT/models 同口径)。
    """
    if (MODELS / name / "sourcecode").is_dir():
        return None
    test_dir = MODELS / name / "test"
    if not test_dir.is_dir():
        return None
    return Unit(id=f"test-{name}", kind="test",
                cos_key=f"{UNITS_PREFIX}/test-{name}.tar.gz",
                sources=[Source(root=test_dir,
                                arc_prefix=f"{ARC_ROOT}/work/models/{name}/test",
                                exclude=tuple(DEFAULT_EXCLUDE_DIRS))],
                models=[name],
                notes="test 脚本+数据+基线(无 sourcecode 模型的独立 test 单元)")


def resolve_tool_unit(name: str, spec: dict) -> Optional[Unit]:
    """工具模型(kind=="tool") → tool-<name> 单元。

    必须显式声明 kind=tool —— 不能用「有 assets/ 无 sourcecode」推断: evmutation
    这类打分模型的 assets/ 是支撑物料(wheel/plmc 源码), 该走 extra_units 精确声明,
    否则整目录打包会错位。

    映射复刻旧 stage_to_cos: assets/ 下目录条目 X 的内容 → models/<name>/;
    文件条目 X → models/X(gnina.1.3.2 / caver_3.0.2.zip / foldseek 落 models/ 顶)。
    """
    assets = MODELS / name / "assets"
    if spec.get("kind") != "tool" or not assets.is_dir():
        return None
    u = Unit(id=f"tool-{name}", kind="tool", cos_key=f"{UNITS_PREFIX}/tool-{name}.tar.gz",
             models=[name])
    for entry in sorted(assets.iterdir()):
        if entry.is_dir():
            u.sources.append(Source(root=entry, arc_prefix=f"{ARC_ROOT}/models/{name}",
                                    exclude=tuple(DEFAULT_EXCLUDE_DIRS)))
        else:
            # 文件条目: root=文件本身, arc_prefix=目标目录(pack_unit 的 is_file 分支
            # 产出 arc_prefix/<文件名>, 不会误遍历父目录)
            u.sources.append(Source(root=entry, arc_prefix=f"{ARC_ROOT}/models"))
    return u


def resolve_extra_units(name: str, spec: dict) -> List[Unit]:
    """model.json 的 extra_units: 约定之外的附加单元(如 evmutation 的 plmc)。

    声明: {"id": "tool-plmc", "pack": ["assets/plmc"], "dest": "bin/plmc"}
    dest 为实例端相对 dockbuddy 根的路径; pack 条目为目录时其内容映射到 dest,
    为文件时文件本身落 dest/ 下。
    """
    out = []
    for ex in spec.get("extra_units") or []:
        dest_rel = _rel_dock(ex.get("dest", ""))
        sources = []
        for p in ex.get("pack") or []:
            local = MODELS / name / p
            if local.is_dir():
                sources.append(Source(root=local, arc_prefix=f"{ARC_ROOT}/{dest_rel}",
                                      exclude=tuple(DEFAULT_EXCLUDE_DIRS)))
            elif local.is_file():
                sources.append(Source(root=local, arc_prefix=f"{ARC_ROOT}/{dest_rel}"))
        if sources:
            uid = ex.get("id") or f"extra-{name}"
            out.append(Unit(id=uid, kind="extra", cos_key=f"{UNITS_PREFIX}/{uid}.tar.gz",
                            sources=sources, models=[name], notes=ex.get("notes", "")))
    return out


def resolve_units(names: Optional[List[str]] = None) -> List[Unit]:
    """解析全部(或指定)模型的部署单元。

    names=None(--all)时才带共享单元(shared-miniconda); 指定模型时不带,
    避免快速单模型打包白打 198M 安装包。
    """
    units: List[Unit] = []
    for name in (names or all_models()):
        spec = load_spec(name)
        # 源码单元(src-<m>, test/ 同包) 优先; 无 sourcecode 时退 test 独立单元。
        # tool 单元(kind=tool 的 assets) 与 extra_units 独立并列 —— 工具模型会同时有
        # tool-<m>(资产) + test-<m>(测试) 两个单元, 互不冲突(arcname 前缀不同)。
        src = resolve_src_unit(name, spec)
        if src:
            units.append(src)
        else:
            test = resolve_test_unit(name, spec)
            if test:
                units.append(test)
        tool = resolve_tool_unit(name, spec)
        if tool:
            units.append(tool)
        units.extend(resolve_extra_units(name, spec))
    if names is None:
        units.extend(resolve_shared_units())
    return units


def resolve_shared_units() -> List[Unit]:
    """共享单元: 不属于任何模型、但随镜像走的安装期大文件。

    目前只有 Miniconda 安装器(198M): sftp 传它会抖(2026-10-14 10054 的教训),
    必须走 COS 单元; setup_base.sh 从 models/ 取它装到 /home/ubuntu/miniconda3。
    pipeline 代码/测试数据走 sftp(小、常变), 刻意不打单元。
    """
    mc = MODELS / "Miniconda3-latest-Linux-x86_64.sh"
    if not mc.is_file():
        return []
    return [Unit(id="shared-miniconda", kind="shared",
                 cos_key=f"{UNITS_PREFIX}/shared-miniconda.tar.gz",
                 sources=[Source(root=mc, arc_prefix=f"{ARC_ROOT}/models")],
                 models=["(shared)"],
                 notes="Miniconda 安装器 198M; setup_base.sh 装到 /home/ubuntu/miniconda3")]


def weights_manifest(names: Optional[List[str]] = None) -> Dict[str, list]:
    """权重清单(实例端 pull 用): {model: [{cos, dest, layer, extract?}]}。

    不打包权重, 只把 model.json 的 weights 声明翻成实例端可直接消费的清单。
    dest 相对 MODELS_ROOT/<model>/(与旧 pull_models 口径一致)。
    """
    out: Dict[str, list] = {}
    for name in (names or all_models()):
        spec = load_spec(name)
        ws = []
        for w in spec.get("weights") or []:
            cos = str(w.get("cos", ""))
            entry = {"cos": cos, "dest": str(w.get("dest", "")),
                     "layer": cos.split("/")[0] if "/" in cos else "hot"}
            if w.get("extract"):
                entry["extract"] = w["extract"]
            ws.append(entry)
        if ws:
            out[name] = ws
    return out


# ---------------------------------------------------------------- 打包
# 压缩器分工(用户 2026-10-15 指定「用系统安装的 PeaZip」):
#   ① Python tarfile **无压缩** tar —— 纯 I/O, 快; arcname 精确控制(_iter_files
#      已应用排除), 无需 staging 树(硬链接/批量删除都不要, 后者会撞 safe-delete);
#   ② 系统 PeaZip(C:\Program Files\PeaZip\peazip.exe) -add2gzip 做**压缩**——
#      压缩才是慢的那一步, 交给系统工具。PeaZip CLI 坑(已踩): 未定义开关(如
#      -add2tgz)会弹 GUI 干等; -add2tar/-add2gzip 的输出名由**输入名派生**
#      (home → home.tar), 首个参数不是输出名。
#   PeaZip 缺失时退化 Python gzip(level 6, 可移植性保险, 会打印警告)。
PEAZIP = os.environ.get("PEAZIP", r"C:\Program Files\PeaZip\peazip.exe")


def _iter_files(root: Path, exclude: Tuple[str, ...]):
    """遍历 root 下文件(应用排除), yield (abs, rel_posix)。"""
    for dirpath, dirnames, filenames in os.walk(root):
        # 目录级排除(原地剪枝, 避免遍历 .git 67M)
        dirnames[:] = [d for d in dirnames
                       if not _excluded(str((Path(dirpath) / d).relative_to(root)).replace(os.sep, "/"),
                                        exclude)]
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = str(p.relative_to(root)).replace(os.sep, "/")
            if fn.endswith(DEFAULT_EXCLUDE_SUFFIX):
                continue
            if _excluded(rel, exclude):
                continue
            yield p, rel


def _run_peazip(args: List[str]) -> None:
    """跑 PeaZip CLI 并校验关键产物存在(它退出码恒 0, 不能信)。"""
    subprocess.run([PEAZIP] + args, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=3600)


def content_sha(unit: Unit) -> str:
    """单元**源内容**哈希(与压缩无关): 对 (arcname, 文件 sha256) 排序后 sha256。

    供增量打包对比用 —— manifest 里的 `sha256` 是**压缩后 tar.gz 文件**的哈希,
    压缩器/时间戳/压缩级别一变字节流就变, 无法判断「源内容是否真的变了」。本函数
    只 hash 源文件字节 + 其在 tar 内的 arcname, 源没变 → 哈希不变 → 可跳过重打包。
    """
    h = hashlib.sha256()
    entries = []
    for src in unit.sources:
        if src.root.is_file():
            entries.append((f"{src.arc_prefix}/{src.root.name}",
                            hashlib.sha256(src.root.read_bytes()).hexdigest()))
        else:
            for p, rel in _iter_files(src.root, src.exclude):
                entries.append((f"{src.arc_prefix}/{rel}",
                                hashlib.sha256(p.read_bytes()).hexdigest()))
    for arc, fh in sorted(entries):
        h.update((arc + "\0" + fh + "\n").encode("utf-8"))
    return h.hexdigest()


def pack_unit(unit: Unit, out_dir: Path, content_sha_value: str = "") -> dict:
    """打包一个单元 → out_dir/<id>.tar.gz, 返回 manifest 条目。

    产物 arcname 均带 home/ubuntu/ 前缀(解包即落位)。中间 tar 单文件、用完即删
    (不做任何批量删除——环境 safe-delete 对 >50 文件的删除会拦截)。

    content_sha_value: 调用方预先算好的 content_sha(增量打包时复用, 避免二次遍历);
    传空则不在 manifest 条目里写 content_sha(兼容旧调用)。
    """
    import gzip

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{unit.id}.tar.gz"
    tar_mid = out_dir / f".{unit.id}.tmp.tar"     # 无压缩 tar(纯 I/O)

    n = 0
    with tarfile.open(tar_mid, "w") as tf:
        for src in unit.sources:
            if src.root.is_file():
                tf.add(src.root, arcname=f"{src.arc_prefix}/{src.root.name}")
                n += 1
                continue
            for p, rel in _iter_files(src.root, src.exclude):
                tf.add(p, arcname=f"{src.arc_prefix}/{rel}")
                n += 1
    if n == 0:
        tar_mid.unlink()
        raise RuntimeError(f"{unit.id}: 内容为空(源不存在或全被排除?)")

    if os.path.isfile(PEAZIP):
        gz_mid = out_dir / f".{unit.id}.tmp.tar.gz"
        _run_peazip(["-add2gzip", str(tar_mid)])
        if not gz_mid.is_file():
            tar_mid.unlink()
            raise RuntimeError(f"{unit.id}: PeaZip -add2gzip 未产出(退出码恒 0 不可信)")
        shutil.move(str(gz_mid), str(out))
        tar_mid.unlink()
        backend = f"peazip({os.path.basename(PEAZIP)})"
    else:
        print(f"  [warn] PeaZip 不存在({PEAZIP}), 退化 Python gzip level6(慢)", flush=True)
        with open(tar_mid, "rb") as fi, gzip.open(out, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo, 1 << 20)
        tar_mid.unlink()
        backend = "python-gzip(fallback)"

    size = out.stat().st_size
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    meta = {"cos_key": unit.cos_key, "kind": unit.kind, "size": size,
            "sha256": h.hexdigest()[:16], "files": n, "models": unit.models,
            "apply": unit.apply, "notes": unit.notes, "backend": backend}
    if content_sha_value:
        meta["content_sha"] = content_sha_value
    return meta


# ---------------------------------------------------------------- 自检
def _ok_arc(name: str) -> bool:
    """arcname 白名单: home / {ARC_HOME} / {ARC_HOME}/ 之下。

    PeaZip 的 tar 含目录条目(home、home/ubuntu、...), Python tarfile 只含文件
    条目(旧实现逐文件 add), 两者都要放行。
    """
    return name in (ARC_HOME_FIRST, ARC_HOME) or name.startswith(ARC_HOME + "/")


def selfcheck(units: List[Unit], packed: Dict[str, dict]) -> List[str]:
    """返回错误列表(空=通过); warning 不进列表, 由调用方打印。"""
    errors: List[str] = []
    arc_seen: Dict[str, str] = {}
    for u in units:
        meta = packed.get(u.id)
        if not meta:
            errors.append(f"{u.id}: 未打包")
            continue
        out = BUILD / "units" / f"{u.id}.tar.gz"
        # 1. tar 可读 + 2. arcname 白名单 + 3. 跨单元无同路径冲突
        try:
            with tarfile.open(out, "r:gz") as tf:
                for m in tf.getmembers():
                    if not _ok_arc(m.name):
                        errors.append(f"{u.id}: arcname 越权 {m.name}")
                    if m.isdir():
                        continue   # 目录条目跨单元共享属正常(各单元都含前缀树)
                    if m.name in arc_seen:
                        errors.append(f"{u.id}: arcname 与 {arc_seen[m.name]} 冲突 {m.name}")
                    arc_seen[m.name] = u.id
        except Exception as e:  # noqa: BLE001
            errors.append(f"{u.id}: tar 不可读({type(e).__name__}: {e})")
        # 4. patches 与 sourcecode 一致性
        if u.apply:
            patch_root = next((s.root for s in u.sources
                               if s.arc_prefix.endswith(f"/_patches/{u.models[0]}")), None)
            src_root = next((s.root for s in u.sources
                             if not s.arc_prefix.endswith(f"/_patches/{u.models[0]}")), None)
            if patch_root and src_root:
                for p, rel in _iter_files(patch_root, ()):
                    counterpart = src_root / rel
                    if not counterpart.is_file():
                        continue          # 新增型补丁: 合法, 记 warning(调用方)
                    a = p.read_bytes().replace(b"\r\n", b"\n")
                    b = counterpart.read_bytes().replace(b"\r\n", b"\n")
                    if a != b:
                        errors.append(f"{u.id}: 补丁与源码不一致 {rel}")
    return errors


def patch_warnings(units: List[Unit]) -> List[str]:
    """补丁文件在源码中不存在(新增型)或源码无对应(反向漂移)的 warning 列表。"""
    warns = []
    for u in units:
        if not u.apply:
            continue
        patch_root = next((s.root for s in u.sources
                           if s.arc_prefix.endswith(f"/_patches/{u.models[0]}")), None)
        src_root = next((s.root for s in u.sources
                         if not s.arc_prefix.endswith(f"/_patches/{u.models[0]}")), None)
        if patch_root and src_root:
            for p, rel in _iter_files(patch_root, ()):
                if not (src_root / rel).is_file():
                    warns.append(f"{u.id}: 补丁 {rel} 在源码中不存在(新增型?)")
    return warns


def check_weights_declared(names: Optional[List[str]] = None) -> List[str]:
    """5. weights 声明的路径 sanity(本地存在性不强制——权重住 COS, 本地不必存)。

    查: dest 不能是绝对路径/含 '..'(防解包穿越); 本地有对应文件时记录条数。
    COS key 存在性校验属网络检查, 归 Phase 2(check_model_paths 等价物)。
    """
    errors = []
    for name in (names or all_models()):
        for w in load_spec(name).get("weights") or []:
            dest = str(w.get("dest", ""))
            if not dest:
                continue
            if dest.startswith("/") or ".." in dest.split("/"):
                errors.append(f"{name}: weights dest 非法 {dest!r}")
    return errors
