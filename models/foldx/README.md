# FoldX 5.1 ΔΔG —— score

FoldX 5.1 BuildModel 真稳定性 ΔΔG, 本地 CPU。

## assets/ 内容（纯资源，均不入 git）

- `foldx/`

## setup.sh 做的事

foldx/ 目录(foldx_20261231 + rotabase.txt + molecules/)整体落位 /home/ubuntu/foldx/。

## 踩坑记录（踩一个记一个）

1. rotabase.txt 必须与二进制同目录。
2. FOLDX_BIN 环境变量或 --bin 指定二进制。

## 验证命令

```bash
/home/ubuntu/foldx/foldx_20261231 --help 2>&1 | head -1
```
