# 共享资源(ESM-2 骨干 + conda) —— shared

ESM-2 650M 骨干(esm2_t33_650M_UR50D.pt)是 VenusREM/GeoStab/EvolvePro 的共同特征骨干; Miniconda 安装器用于 GeoStab 等需要 conda 环境的模型。

## assets/ 内容（纯资源，均不入 git）

- `esm2_t33_650M_UR50D.pt`
- `Miniconda3-latest-Linux-x86_64.sh`

## setup.sh 做的事

esm2 权重落位 /home/ubuntu/dockbuddy/models/esm2/ 或 torch hub 缓存 /root/.cache/torch/hub/checkpoints/。

## 踩坑记录（踩一个记一个）

1. esm2_t33_650M_UR50D.pt(2.6GB) 是 ESM-2 650M, 不是 esm1v; 别与 esm1v_t33_650M_UR90S_* 混。
2. 多个模型(VenusREM/GeoStab/EvolvePro)共享这份骨干, 只装一次。

## 验证命令

```bash
python3 -c "import esm; m,_=esm.pretrained.esm2_t33_650M_UR50D(); print('esm2 ok')"
```
