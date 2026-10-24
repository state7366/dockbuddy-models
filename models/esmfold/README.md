# ESMFold 折叠 —— fold

ESMFold 3B 折叠(结构回测), 本地 GPU 推理 + 公共 API 双通道。

## assets/ 内容（纯资源，均不入 git）

- `esmfold_3B_v1.pt`
- `openfold/`
- `openfold.tar.gz`
- `dllogger/`
- `dllogger.tar.gz`

## setup.sh 做的事

esmfold_3B_v1.pt 落位 torch hub 缓存; openfold/dllogger 先 pip install ./dllogger 再 pip install --no-deps ./openfold。

## 踩坑记录（踩一个记一个）

1. openfold 在实例上 git clone 会卡, 需本地下载再上传(见 assets)。
2. openfold 编译 CUDA 扩展需 nvcc, 失败回退 --no-deps 纯 Python(推理够用)。
3. dllogger 必须先于 openfold 装。
4. 公共 API 通道(api.esmatlas.com)无需 GPU, ≤400aa。

## 验证命令

```bash
python3 -c "import esm; esm.pretrained.esmfold_v1(); print('esmfold ok')"
```
