# modeller —— 同源建模工具(salilab, 学术免费)

> 按「每个模型自我维护」原则, 本目录自带 `model.json`(部署声明) +
> `test/`(自测脚本 + 基线)。2026-10-14 从 `deploy/setup_modeller.sh` 迁来。

## 为什么改成 conda 装

原 `deploy/setup_modeller.sh` 走 **deb 包 + `dpkg -i` + `sudo` 写 `/etc/profile.d/`**:

| 问题 | 说明 |
|---|---|
| 需要 root | `dpkg -i` 必须 sudo, 与「资源全在 ubuntu 家目录、不用 root、不碰系统目录」约定冲突 |
| deb 不在仓库也不在 COS | 脚本里三个候选路径都找不到 deb(本机与 COS 均无此文件), 实际是**跑不起来的孤儿脚本** |
| 环境割裂 | 系统级安装, 不进 conda env, 无法随 `dockbuddy` 环境一起快照进制镜像 |

改用 conda:

```bash
conda install -n dockbuddy -y -c salilab 'modeller=10.8'
```

- 无需 root, 落 `$HOME/miniconda3/envs/dockbuddy/`, 完全在 ubuntu 家目录下
- **同时提供 `mod10.8` 二进制和 `modeller` Python 包** → pipeline 的两条调用路径
  (`MODELLER_BIN` / `MODELLER_DIR`) 都通
- 与 deb 版同版本号 10.8, 功能等价
- linux-64 上有 py36~py314 多个 build, 主环境 Python 3.10 可直接匹配

`model.json` 里用 `conda` 字段声明(该字段即为此新增, 见
`deploy/dcommon/instance.py::_install_deps`)。

## License key

Modeller 学术免费, 官方通用 key = `MODELIRANJE`, 已硬编码在
`pipeline/libdock/external_tools.py:113 DEFAULT_MODELLER_KEY`。
调用时经 `KEY_MODELLER` 环境变量注入, **无需任何额外配置**。

## pipeline 入口

```
components/stability.py  stability_modeller()
    → libdock/external_tools.py  modeller_model(alignment, knowns, sequence, ...)
        → 定位: MODELLER_BIN(mod10.8) 优先, 回退 MODELLER_DIR(modlib)
        → 生成 automodel 脚本并执行, 输出 <sequence>.B9999000*.pdb
```

CLI: `python pipeline/dockbuddy.py modeller --input aln.ali --knowns T --sequence S`

## 自测

`test/test.py` 验三层(秒级, smoke 定位):

| 字段 | 含义 |
|---|---|
| `import_ok` | `import modeller` 成功 —— conda 包就位 |
| `environ_ok` | `Environ()` 构造成功 —— **license key 的校验点**, key 无效直接抛错 |
| `modlib_libs` | 读入的 modlib 力场库数(2 = `top_heav.lib` + `par.lib`), 证明约 30MB 数据文件完整 |

**没做**真实 automodel 建模: 需模板 PDB + PIR 对齐输入、耗时分钟级, 与 smoke 秒级
定位不符; 真实链路由 pipeline 的 `modeller_model()` 覆盖。

Baseline 目前是「未实测」占位, 首次真跑通过后回填 actual 值。
