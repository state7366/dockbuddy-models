# EVmutation 上位性(DCA) —— score

EVmutation(evcouplings + plmc)残基耦合上位性预测, 非单点打分。

## assets/ 内容（纯资源，均不入 git）

- `plmc/`
- `plmc.tar.gz`

## setup.sh 做的事

plmc 源码编译后二进制落位 /usr/local/bin/plmc。

## 踩坑记录（踩一个记一个）

1. plmc 需编译(cmake + gcc); 也可用 plmc.tar.gz。
2. 需要 a3m(MSA) 输入, 6417 条 PBATase MSA 已构建。

## 验证命令

```bash
plmc -h 2>&1 | head -1
```
