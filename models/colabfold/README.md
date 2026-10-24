# ColabFold 折叠 —— fold

ColabFold(AF2 multimer_v3)单序列/MMSA 折叠。

## assets/ 内容（纯资源，均不入 git）

- `alphafold_params_colab_2022-12-06.tar`

## setup.sh 做的事

权重解压到 ~/.cache/colabfold/params(需 touch download_complexes_multimer_v3_finished.txt)。

## 踩坑记录（踩一个记一个）

1. cudnn 9.8.0.87 是 ColabFold+torch 的唯一兼容解。
2. 单序列模式 pLDDT 偏低(实测 32.8), 属正常。

## 验证命令

```bash
colabfold_batch --help 2>&1 | head -1
```
