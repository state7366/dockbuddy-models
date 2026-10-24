# ESM-1v zero-shot 打分 —— score

Meta ESM-1v, 5 种子集成伪对数似然, 代理打分(不预测 kcat/Km)。

## assets/ 内容（纯资源，均不入 git）

- `(权重 5×7.8GB 走 torch hub, 不本地化; 见 pitfalls)`

## setup.sh 做的事

权重由 fair-esm 自动下载到 torch hub 缓存(受 TORCH_HOME 控制); 无需手动落位。

## 踩坑记录（踩一个记一个）

1. 5 个种子 esm1v_t33_650M_UR90S_{1..5}.pt 各 7.8GB, 合计 ~39GB, 本地不落、走 torch hub 或镜像固化。
2. zero-shot 伪对数似然是代理指标, 不预测活性; 报告须标注。
3. 镜像 v6 已固化 fair-esm + 权重。

## 验证命令

```bash
python3 -c "import esm; m,_=esm.pretrained.esm1v_t33_650M_UR90S_1(); print('esm1v ok')"
```
