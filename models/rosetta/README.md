# PyRosetta 精细 ΔΔG —— score

PyRosetta cartesian_ddg 精细 ΔΔG(与 FoldX 并列, 按需切换)。

## assets/ 内容（纯资源，均不入 git）

- `pyrosetta-2026.29+releasequarterly.80a0635615-cp310-cp310-linux_x86_64.whl`

## setup.sh 做的事

pip install --no-index --find-links . pyrosetta(用 assets 里的 wheel)。

## 踩坑记录（踩一个记一个）

1. 非商业许可(学术免费, 填一次免费表单; 商业另购)。
2. 2026-01 起 quarterly builds 免 license key。
3. 无 Windows 原生 wheel, Windows 走 WSL/Linux。

## 验证命令

```bash
python3 -c "import pyrosetta; print('pyrosetta ok')"
```
