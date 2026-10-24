# OrthologTransformer —— 跨物种基因重设计

> 把某物种的编码 DNA(CDS) 改写为目标宿主的适配版本（同义替换为主，改信号肽 + 保守非同义 + 小 indel）。
> Nat.Commun. 2026, DOI 10.1038/s41467-026-69966-0。仓库 `github.com/mana438/OrthologTransformer`。
> 接入 DockBuddy：`pipeline/scoring/ortholog.py`（adapter `ortholog`, kind=redesign）+ 顶层命令 `dockbuddy ortholog`。

## assets/ 内容（纯资源，均不入 git）

| 文件 | 大小 | 用途 | 落位（实例） |
|---|---|---|---|
| `aligned_model.pt` | 435 MB | 对齐约束版权重（推荐，稳定） | `/home/ubuntu/dockbuddy/models/ortholog/aligned_model.pt` |
| `unaligned_model.pt` | 435 MB | 无对齐版（SOTA，建议 beam search） | 同上 |
| `ortholog_vocab.json` | 68 KB | 2206 token（含 2138 细菌物种 OMA ID） | 随 `pipeline/scoring/` 代码（已入库） |

> 模型定义（CodonTransformer）已在 `pipeline/scoring/ortholog.py` 内嵌，**不依赖原仓库运行时**。
> 推理只需 `torch>=2.0 + biopython + numpy`（pandas/scipy/matplotlib/ViennaRNA 仅训练/MCTS 需要，**不装**）。

## setup.sh 做的事

1. `pip install torch biopython numpy`（实例已装则跳过）。
2. 把 `assets/{aligned,unaligned}_model.pt` 复制到 `/home/ubuntu/dockbuddy/models/ortholog/`（或 `DOCK_MODELS_DIR`）。
3. 自检：`torch.load(aligned_model.pt, map_location='cpu')` 可读 + 模型超参匹配。

## 踩坑记录（踩一个记一个）

1. **模型超参**：`d_model=512, nhead=16, encoder=decoder=20, dim_feedforward=1024, dropout=0.0`。
   ⚠️ `dim_feedforward` 是 **1024 不是 2048**、`dropout` 是 **0.0 不是 0.1** —— 写错则
   `load_state_dict(strict=True)` 直接抛尺寸不匹配。
2. **token→DNA 解码**：vocab 里密码子占索引 **3..66**；`<pad>/<bos>/<eos>`=0/1/2，gap `---`=67，
   **物种 ID 从 68 起**。解码必须只保留 3..66，否则物种 ID（如 BACSU=916）会混进输出 DNA 导致翻译错位。
3. **高 GC 序列 greedy 退化（最坑）**：放线菌源 CDS（如 PBATase，GC 70.2%、密码子第三位 96.8%）时，
   greedy **不生成 EOS 终止密码子**，跑满 max_len（输出 2100bp 垃圾尾巴）。实测前 N 密码子翻译
   与源蛋白 **100% 一致**，仅缺终止子。解法：`dockbuddy ortholog --fixed-aa-len <源蛋白aa数>`
   （固定生成长度 + 自动补 TAA），或 `--beam-size 20`（需 GPU）。
4. **beam search 必须批量 forward**：逐 beam forward 版在 V100 上 GPU 利用率仅 6%（卡在 Python
   循环 + `.item()` 同步），批量堆 batch 一次 forward 才正常（快 ~beam_size 倍）。
5. **单步 forward 慢是环境固有**：V100 + torch 2.5.1 + 40 层 Transformer + batch=1 + `norm_first=True`
   → 单次 forward ~400ms。torch.compile / nested-tensor 开关 / fp16 均无效（~405ms 不变）。
   252 aa ≈ 100s/条。若嫌慢，换 A100/H100（快 3-5 倍），或接受串行。
6. **V100 不支持 bf16**：官方 `autocast(bfloat16)` 会崩，改 fp32。
7. **源物种必须在 vocab**：模型只在 2138 细菌物种上训练。`Dactylosporangium aurantiacum`（PBATase
   来源）不在表内，用同科 `Micromonospora`（`MICSL`）作代理条件（对"改写到目标宿主"影响小）。
   **酵母/真菌完全不在表内**（无 `YEAST`/`SACCE`），酵母表达需另走标准密码子优化。
8. **ViennaRNA 只在 MCTS 用**：推理/beam search 不需要，Windows 装不了也不影响。

## 验证命令

```bash
# 用论文自带 IsPETase 输入复现（应得大肠杆菌风格信号肽、催化核心保留）
python pipeline/dockbuddy.py ortholog \
  --source-fasta <IDESA CDS fasta> --source-species IDESA --target-species ECOLI \
  --model-path deploy/models/ortholog/assets/aligned_model.pt
# PBATase（高 GC）退化场景：固定长度 + 补终止子
python pipeline/dockbuddy.py ortholog \
  --source-dna <CDS> --source-species MICSL --target-species ECOLI \
  --fixed-aa-len 252 --model-path deploy/models/ortholog/assets/aligned_model.pt
```
