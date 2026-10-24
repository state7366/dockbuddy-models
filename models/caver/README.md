# CAVER 3.0 通道分析 —— tunnel

CAVER 3.0(Java)口袋通道几何, 独立于自研口径的第三方参照。

## assets/ 内容（纯资源，均不入 git）

- `caver_3.0.2.zip`

## setup.sh 做的事

解压到 /home/ubuntu/caver/, 入口 caver.ui.Launcher。

## 踩坑记录（踩一个记一个）

1. 纯 Java, 需 JRE, CPU 即可。
2. 起始点用 starting_point_atom <原子序号>。

## 验证命令

```bash
java -version 2>&1 | head -1
```
