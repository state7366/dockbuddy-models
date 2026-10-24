# GNINA CNN 重打分 —— dock

GNINA 1.3.2 深度学习增强对接(CNNscore/affinity), 与 Vina 互补。

## assets/ 内容（纯资源，均不入 git）

- `gnina.1.3.2`

## setup.sh 做的事

二进制落位 /home/ubuntu/gnina。

## 踩坑记录（踩一个记一个）

1. 需 LD_LIBRARY_PATH 指向 pip 的 nvidia lib(/usr/local/lib/python3.10/dist-packages/nvidia/*/lib)。
2. 预编译二进制省去 CUDA+OpenBabel3+libmolgrid 编译。
3. CNN 打分作软指标(rescore), 不替代 Vina 硬约束。

## 验证命令

```bash
LD_LIBRARY_PATH=/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib:/usr/local/lib/python3.10/dist-packages/nvidia/cudnn/lib /home/ubuntu/gnina --help 2>&1 | head -1
```
