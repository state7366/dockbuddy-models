# SaProt 结构感知 PLM —— score

SaProt(残基+3Di 结构 token 对)零样本突变打分, 需 Foldseek 编码结构。

## assets/ 内容（纯资源，均不入 git）

- `SaProt_650M_AF2.pt`
- `pytorch_model.bin`
- `saprot_repo/`

## setup.sh 做的事

权重落位 /home/ubuntu/dockbuddy/repos/SaProt/weights/SaProt/SaProt_650M_AF2/(pytorch_model.bin + .pt); saprot_repo 提供 config/vocab/tokenizer。

## 踩坑记录（踩一个记一个）

1. ⚠️ 必须结构感知序列(残基+3Di token 对, 如 MdEvVpQpLrVyQdYaKv): 纯氨基酸序列全部映射 UNK(实测 'V' not in vocab, 'Vd' in vocab), 打分无意义。需 WT 结构 PDB/CIF → Foldseek structureto3didescriptor 编码。
2. transformers 必须精确 4.28.0(否则加载报错)。
3. peft 仅 LoRA 微调需要, 零样本打分免。
4. 无需 conda: 系统 Python + 上述 pip 即可端到端跑通。

## 验证命令

```bash
python3 -c "from transformers import EsmForMaskedLM; print('saprot deps ok')"
```
