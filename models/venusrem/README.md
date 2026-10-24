# VenusREM 检索增强突变效应 —— score

VenusREM(vrh + ESM-2 骨干 + MSA + Foldseek)突变效应代理分。

## assets/ 内容（纯资源，均不入 git）

- `(无独立权重: vrh 走 pip, ESM-2 骨干见 _common)`

## setup.sh 做的事

ESM-2 骨干用 _common 的 esm2_t33_650M_UR50D.pt。

## patches/ —— 对上游 sourcecode 的本地修改（**必须入库**）

`sourcecode/` 被 `.gitignore` 排除（第三方上游代码不入库），所以对它的修改**如果只
留在 sourcecode/ 里就会永久丢失**。本目录保存这些修改的**唯一入库副本**。

| 补丁文件 | 对应上游路径 | 改了什么 |
|---|---|---|
| `patches/vrh/baseline/esm2/esm2.py` | `sourcecode/VenusREM-Harness/vrh/baseline/esm2/esm2.py` | 让 `load_esm2_model()` 支持 `ESM2_LOCAL_PATH` 环境变量，优先从本地路径加载 ESM-2 权重 |

> 2026-10-15：补丁按「仓库内相对路径」重组（原扁平名 `vrh_baseline_esm2.py`），
> 由 `deploy/apply_model_patches.sh` 在两条路径**自动**应用（此前为手工 cp）：
> 制镜像——`setup_v9.sh` 在 `pip install` 前覆盖到 `LOCAL_ASSETS/VenusREM-Harness`
> （pip 是拷贝式安装，装后再打不生效）；跑测试——`instance.py` `_install_deps`
> sftp 上传 sourcecode 后覆盖到 `repos/VenusREM-Harness/VenusREM-Harness`
> （model.json `repo.repo_subdir` 声明）。详见 `deploy/models/README.md`。

### 为什么必须打这个补丁

上游 `vrh` 的 ESM-2 baseline 直接 `AutoModelForMaskedLM.from_pretrained("facebook/
esm2_t33_650M_UR50D")` → 走 HF 外网下载。实例上这条路**又慢又贵**（HF Hub 已废弃，
且经代理有请求体大小上限）。打补丁后 `pipeline/scoring/venusrem.py:59-65` 设
`ESM2_LOCAL_PATH` 指向 COS 内网拉下来的权重，全链路不出公网。

### 重新 clone sourcecode 后怎么恢复

```bash
# 方式一(推荐, 与部署路径同一工具): 应用到本地 sourcecode 树
bash ../../apply_model_patches.sh patches sourcecode/VenusREM-Harness
# 方式二(手动, 单文件):
cp patches/vrh/baseline/esm2/esm2.py \
   sourcecode/VenusREM-Harness/vrh/baseline/esm2/esm2.py
```

> 2026-10-14 从 `deploy/patches/` 迁到本目录（每个模型的东西放各自文件夹内自我维护）。
> 2026-10-15 改为按仓库内相对路径组织 + 双路径自动应用（见上）。

## 踩坑记录（踩一个记一个）

1. 需要 MSA(同源序列) + Foldseek 编码, 缺 MSA 时效果差。
2. ESM-2 骨干与 GeoStab/EvolvePro 共享, 只装一份。
3. **改了 sourcecode/ 里的文件一定要往 `patches/` 存一份**，否则下次重 clone 就丢了
   （sourcecode/ 不入库，见上）。

## 验证命令

```bash
python3 -c "import vrh; print('vrh ok')"
```
