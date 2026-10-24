# GeoStab GeoDDG/GeoDTm 稳定性 —— score

GeoStab-suite(GeoDDG/GeoDTm/GeoFitness)热稳定性与稳定性预测。

## 部署口径(v9 镜像, 2026-10-15)

- conda 独立环境 `geostab`(py3.10), torch 符号链接复用 `dockbuddy` env 的 torch 2.5.1+cu121
  (官方 README 的 torch 1.13 与主环境冲突, 实测 2.5.1 可跑; 见 setup_v9.sh step9)。
- 仓库落位 `/home/ubuntu/dockbuddy/models/geostab`(run.sh 是运行入口, 硬编码
  `conda activate geostab`, cleanup 时保留); 跑测试路径由 `_install_deps` sftp 上传到
  `repos/GeoStab/GeoStab`(model.json `repo_subdir` 声明)。
- 权重 `warm/geostab/GeoStab.tar.gz` 只定向提取 `model_*/model.pt`(tarball 内源码是旧版,
  整包解压会覆盖已打补丁的源码; 见 setup_from_cos.sh step3)。

## patches/ —— 对上游 sourcecode 的本地修改(**必须入库**, 2026-10-15 拆解)

`sourcecode/` 被 `.gitignore` 排除, 对它的修改只留 sourcecode/ 会随重 clone 丢失。
本目录是唯一入库副本, 按仓库内相对路径存**修复后完整文件**, 由
`deploy/apply_model_patches.sh` 在两条路径自动应用(制镜像: setup_v9.sh step9;
跑测试: instance.py `_install_deps`)。详见 `deploy/models/README.md`。

| 补丁文件 | 改了什么 |
|---|---|
| `run.sh` | ① wt 段串行化: 上游 5×esm1v + esm2 + fixed 全 `&` 并行, 单进程 anon-rss 峰值实测 9.7G(权重 7.8G/个), 4C19G 机型必触发 OOM killer(syslog 实锤两次 Killed); 且无参 `wait` 在 `set -e` 下静默吞后台失败 → ensemble 报莫名 FileNotFoundError。mut 段仅 fixed+esm2 两进程(~7G)保留并行。 ② 两处 FoldX 调用包 `(cd "$(dirname "${software_foldx}")" && ...)` 子 shell: FoldX RepairPDB/BuildModel 从**当前工作目录**读 rotabase.txt, 而 rotabase.txt 与二进制同目录。 ③ FoldX 二进制四分支自解析(仓库自带 > `$FOLDX_BIN` > PATH > 部署默认路径), 取代部署脚本 sed 改写路径。 ④ CRLF→LF(上游仓库带 CRLF, bash 语法错)。 |
| `generate_features/esm1v_logits.py` | 本地权重(`$ESM1V_DIR` 或 models/esm1v/) + `load_model_and_alphabet_core(..., None)` 跳过 contact 回归头 —— `load_model_and_alphabet_local` 强制要 contact-regression.pt(esm1v 官方权重不含), 本地加载必卡。 |
| `generate_features/esm2_embedding.py` | 同上(esm2 650M; `torch.hub.load` 还会联网下载, 实例不通)。 |

重新 clone sourcecode 后恢复: `bash ../../apply_model_patches.sh patches sourcecode/GeoStab`

## 踩坑记录（踩一个记一个）

1. ⚠️ 命名反直觉: -v threeD 输入结构 PDB、不需 AF2/UniRef30; -v Seq 才需 hhblits+AlphaFold2(暂不接)。
2. 官方 run.sh 一次只处理一个突变(-m/-v/-o 六个参数, mut_info.csv 单行)。
3. FoldX 必须同目录有 rotabase.txt + molecules/(deploy/models/foldx/assets 完整目录,
   由 setup_v9.sh step3 落位 models/foldx/)。
4. ESM-1v/ESM-2 权重由各自 model.json 从 COS 拉到 models/esm1v|esm2/(与 _common 共享 650M 骨干)。
5. threeD 版不需要 AF2/UniRef30; hhblits/AF2 路径是 -v Seq 专用(硬编码 /data3/alphafold, 实例上不可用)。

## 验证命令

```bash
# 镜像内自检(跑测试路径, 自动上传源码+打补丁后):
python deploy/run_model_tests.py all geostab --gpu
# 或手工: bash repos/GeoStab/GeoStab/run.sh -m ddGdTm -v threeD -o <out_dir>
```
