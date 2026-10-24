# 模型库（deploy/models/）

> 本目录是**所有模型/工具的可重新部署单元**。每个子目录以模型名命名，**自包含**——
> 拿到这一整个 `models/` 目录（或其中某个模型子目录）+ 一份干净实例，就能把它重新部署起来。
> 原则：**能 pip/apt 从库安装的（torch/fair-esm/vrh/evcouplings 等）不放进仓库**；
> 其余运行所需（权重、预编译二进制、源码仓库、jar、wheel、vocab）全部放进对应
> `assets/`，做到「离了这个文件夹就无法重新部署」的东西一个不落。

## 目录结构约定

```
models/
├── README.md                 # 本文件：模型清单 + 结构约定 + 自包含原则
├── _common/                  # 跨模型共享资源（非独立模型，命名以下划线开头区分）
│   ├── assets/               #   esm2_t33_650M_UR50D.pt（ESM-2 骨干，VenusREM/GeoStab/EvolvePro 共享）
│   │                         #   Miniconda3-latest-Linux-x86_64.sh（conda 安装器）
│   └── test/data/            #   公共测试数据（wt 序列/变异列表/结构 PDB/MSA）
└── <model>/                  # 每个模型一个目录，**自我维护」
    ├── model.json            #   部署声明（env/python/pip/conda/repo/extra_repos/weights/default）
    ├── assets/               #   纯资源：权重/二进制/源码仓库/jar/wheel/vocab（不入库）
    ├── sourcecode/           #   第三方上游源码（不入库！改了要往 patches/ 存副本）
    ├── patches/              #   对 sourcecode/ 的本地修改（**必须入库**，见下）
    ├── setup.sh              #   部署脚本（pip/apt 依赖 + 资源落位 + 自检，幂等）
    ├── test/                 #   自测（入库）
    │   ├── test.py           #     实例端执行，最后一行打印单行 JSON
    │   ├── data/             #     本模型自带测试数据
    │   └── baseline.json     #     上次实测基线，用于回归比对
    └── README.md             #   部署说明 + 踩坑记录 + 验证命令
```

**命名**：`assets`（复数）放纯资源；旁边 `setup.sh` + `README.md` 是部署脚本与文档。
独立模型的目录用模型名（esm1v/saprot/...），共享资源目录用 `_common` 前缀区分。

**每个模型自我维护**（2026-10-14 约定）：一个模型需要的一切——部署声明、安装入口、
测试数据、测试基线、上游补丁——**都放在它自己的文件夹里**，不要搞一个「大而全」的
脚本把所有模型包进去。调度器（`deploy/run_model_tests.py`）不认识任何具体模型，只按
`model.json` 声明去装环境、按 `test/test.py` 去跑验证。

**`patches/` 为什么必须入库**：`sourcecode/` 被 `.gitignore` 排除（第三方上游代码不
进仓库），所以**对它的修改如果只留在 sourcecode/ 里，下次重新 clone 就永久丢失**。
`patches/` 是这些修改的唯一入库副本，按「仓库内相对路径」组织，存**修复后完整文件**
（非 diff，直接 cp 覆盖）。实例见 `deploy/models/geostab/patches/`（run.sh OOM 串行化
+ FoldX 自解析 + esm1v/esm2 core-loader）与
`deploy/models/venusrem/patches/vrh/baseline/esm2/esm2.py`（ESM2_LOCAL_PATH）。

**`patches/` 怎么被应用（2026-10-15 起全自动，两条路径同一权威源）**：
统一工具 `deploy/apply_model_patches.sh <patches_dir> <target_root>...`（cp 覆盖、
幂等、内容已一致则跳过、目标根不存在则跳过）。model.json 的 `repo.patches` 声明补丁
目录（相对 `models/<模型>/`），`repo.repo_subdir` 声明仓库根在 `repo.dest` 下的子目录
（sftp 上传是「sourcecode 内容平铺进 dest」，只有唯一顶层目录时仓库根为
`dest/<repo_subdir>`，如 geostab 的 `repos/GeoStab/GeoStab`）。
- **制镜像路径**：`stage_to_cos.py` 把 patches 打包进 `sourcecode.tar.gz` 的
  `home/ubuntu/models/_patches/<模型>`（只打包源码进镜像的模型：geostab/venusrem），
  `setup_v9.sh` 用 apply 工具覆盖到落位后的仓库根（venusrem 必须在 `pip install`
  **之前**打，pip 是拷贝式安装）。
- **跑测试路径**：`dcommon/instance.py` `_install_deps` 在 sftp 上传 sourcecode 后，
  把 patches sftp 到同一远程路径并 apply 到仓库根。
补丁只在一处维护（模型各自文件夹），共享脚本零内联补丁。

## 模型清单

| 模型 | kind | 用途 | 本地 assets 状态 | 部署要点 |
|---|---|---|---|---|
| `_common` | — | ESM-2 650M 骨干 + conda | ✅ 已就位（esm2 2.6GB） | VenusREM/GeoStab/EvolvePro 共享骨干 |
| `esm1v` | score | ESM-1v zero-shot | ⚠️ 权重未本地化（5×7.8GB 走 torch hub / 镜像固化） | torch+fair-esm 自动下载 |
| `saprot` | score | SaProt 结构感知 PLM | ✅ 2×2.6GB + config/vocab | 需 Foldseek 编码结构感知序列（⚠️ 纯序列 bug） |
| `venusrem` | score | VenusREM 检索增强 | ⚠️ 无独立权重（vrh pip + esm2 骨干） | 需 MSA + Foldseek |
| `evmutation` | score | EVmutation 上位性 | ✅ plmc 源码 | plmc 编译 + a3m |
| `promep` | score | ProMEP 多模态 | ⚠️ 仓库在，权重无公开下载 | 全量推理受阻 |
| `foldx` | score | FoldX ΔΔG | ✅ 二进制+rotabase | 本地 CPU，rotabase 同目录 |
| `geostab` | score | GeoStab GeoDDG/DTm | ✅ 仓库+权重 | torch1.13 + FoldX + ESM；threeD 版不需 AF2 |
| `rosetta` | score | PyRosetta 精细 ΔΔG | ✅ wheel 1.5GB | 非商业许可，quarterly builds 免 key |
| `esmfold` | fold | ESMFold 折叠 | ✅ 3.5GB 权重 + openfold + dllogger | openfold 编译失败回退 --no-deps |
| `colabfold` | fold | ColabFold 折叠 | ✅ multimer_v3 4.1GB | cudnn 9.8 唯一兼容解 |
| `gnina` | dock | GNINA CNN 重打分 | ✅ 二进制 1.4GB | LD_LIBRARY_PATH 指向 pip nvidia lib |
| `caver` | tunnel | CAVER 通道 | ✅ jar 33MB | Java，纯 CPU |
| `ortholog` | redesign | OrthologTransformer 基因重设计 | ✅ 2×435MB + vocab | 高 GC 退化→fixed_aa_len/beam search |
| `evolvepro` | export | EvolvePro few-shot | ✅ 仓库 50MB | 导出管线用 |
| `proteinmpnn` | generate | ProteinMPNN 反向折叠重设计 | ✅ 仓库+权重 3×6.6MB | 本机 CPU 可跑；`mpnn-redesign` 生成器 |
| `tranception` | score | Tranception 自回归 zero-shot | ⚠️ Small 权重 301MB 已下，需 conda Python 3.8 + transformers 4.17 | 本机 Python 3.13 版本冲突，快机/云部署 |
| `catpred` | score | CatPred kcat 活性 | ⚠️ checkpoint 10.2GB + Linux/GPU | 本机不部署，快机/云部署 |
| `modeller` | modeling | Modeller 同源建模 | ✅ 无 assets（conda 装） | `conda install -c salilab modeller=10.8`，**不用 root**；原 `setup_modeller.sh`（deb + sudo）已删 |

> 镜像固化状态：v6 镜像 `img-499haq3y` 已含大部分模型环境；本目录用于**从零重建**或
> **换实例**时的资源补给。详见 `deploy/镜像安装正向更新计划.md`。

## `model.json` 字段（部署声明，`deploy/dcommon/instance.py` 消费）

| 字段 | 类型 | 说明 |
|---|---|---|
| `env` | str | conda 环境名。缺省 `dockbuddy`；非主环境会先 `conda create -n <env> python=<python>` |
| `python` | str | 独立环境的 Python 版本，缺省 `3.8` |
| `pip` | list | pip 包。两种写法：`"torch==2.1"` 或 `{"spec":"torch==1.13.1","index_url":".../cpu"}`（后者用于 CPU 版 torch 等需独立 index 的包） |
| `conda` | list | **只有 conda channel 才有、pip 装不了的包**。写法 `{"spec":"modeller=10.8","channel":"salilab"}`。用于保持「不碰系统目录、不用 root」——例如 Modeller 官方只提供 deb（`dpkg -i` 需 sudo），走 conda 则落在 conda env 内 |
| `repo` | obj | 本模型源码仓库 `{git, dest}`。本地有 `sourcecode/` 就 sftp 上传，没有才回退 `git clone`（实例连不上 github） |
| `extra_repos` | list | 本模型依赖的**其他**仓库（如 ThermoMPNN/SolubleMPNN 都基于 ProteinMPNN） |
| `weights` | list | `[{cos: "warm/xxx/yyy", dest: "assets/yyy"}]` —— 从 COS **内网**拉 |
| `default` | bool | 是否默认纳入批量安装/验证 |

> ⚠️ **COS 必须走内网**（`cos.<region>.tencentcos.cn`），公网流量要钱且被明令禁止。
> 统一用 `deploy/dcommon/cos.py`，别在临时脚本里重写下载逻辑。

## 自包含重新部署流程（以 ortholog 为例）

```bash
# 1. 上传模型文件夹到实例
scp -r deploy/models/ortholog ubuntu@<ip>:/home/ubuntu/dockbuddy/work/ortholog
# 2. 跑部署脚本（pip 依赖 + 权重落位到 /home/ubuntu/dockbuddy/models/ortholog/）
ssh ubuntu@<ip> "bash /home/ubuntu/dockbuddy/work/ortholog/setup.sh"
# 3. 跑通验证（README.md 里给了自检命令）
```

> 大文件（权重/二进制）**不入 git**（见 .gitignore 的 `deploy/models/`），跨机迁移靠
> 整目录拷贝 / COS / 对象存储。
