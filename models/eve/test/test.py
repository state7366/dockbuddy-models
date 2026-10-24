#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""eve 模型自测脚本(实例端执行)
===================================================================================
由 deploy/run_model_tests.py 调度: 本目录被上传到 /home/ubuntu/dockbuddy/work/models/eve/test/ 后执行。

约定(所有模型一致):
  - 环境变量: COMMON_DATA = 公共测试数据目录(/home/ubuntu/dockbuddy/work/models/_common/test/data)
              MODEL_ROOT  = 本模型权重/资源目录(/home/ubuntu/dockbuddy/models/eve)
              TEST_DATA   = 本模型自带数据目录(/home/ubuntu/dockbuddy/work/models/eve/test/data)
  - 输出: **最后一行**打印单行 JSON, 与 baseline.json 比对判回归。

EVE 口径(2026-10-15 冲刺定稿): **Python API 直推**而非官方 compute_evol_indices.py
CLI——CLI 的 MSA_processing 用默认 focus 阈值 0.3(清洗后 204 列), 而我们的 VAE
checkpoint(2026-10-13 训练, warm/eve/pbatase_vae_checkpoint=torch.save dict)是在
0.5 阈值(189 列)上训练的 → 官方 CLI load_state_dict 尺寸不匹配且其裸 except 只报
"Unable to locate VAE model checkpoint"(极误导, 冲刺实踩 4 轮)。
直推流程: checkpoint 参数建 VAE_model → load_state_dict → 0.5/0.5 阈值 MSA →
单点突变 ΔELBO(EVE 官方语义, 越高越兼容)。
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/ubuntu/dockbuddy/work/pipeline")
sys.path.insert(0, os.environ.get("REPO_DIR", "/home/ubuntu/dockbuddy/repos/EVE"))

COMMON = os.environ.get("COMMON_DATA", "/home/ubuntu/dockbuddy/work/models/_common/test/data")
ROOT = os.environ.get("MODEL_ROOT", "/home/ubuntu/dockbuddy/models/eve")
REPO = os.environ.get("REPO_DIR", "/home/ubuntu/dockbuddy/repos/EVE")

_V = json.load(open(os.path.join(COMMON, "variants.json"), encoding="utf-8"))
WT = _V["wt_seq"]
VAR = _V["variants"]


def run():
    if not os.path.isdir(REPO):
        raise RuntimeError(f"EVE 仓库缺失(REPO_DIR={REPO!r})")
    ckpt_raw = os.path.join(ROOT, "results", "VAE_parameters")
    if not os.path.isfile(ckpt_raw):
        raise RuntimeError(f"VAE checkpoint 缺失(权重未拉?): {ckpt_raw}")
    msa = os.path.join(ROOT, "data", "MSA", "pbatase.a2m")
    if not os.path.isfile(msa):
        raise RuntimeError(f"家族 MSA 缺失: {msa}")

    import torch
    from utils import data_utils                      # noqa: E402 (EVE 仓库)
    from EVE import VAE_model                         # noqa: E402

    ckpt = torch.load(ckpt_raw, map_location="cpu")

    # MSA 用**训练同款阈值**(0.5/0.5 → 189 focus 列); 官方默认 0.3 会得 204 列致
    # 权重尺寸不匹配。
    data = data_utils.MSA_processing(
        MSA_location=msa, theta=0.2, use_weights=False,
        preprocess_MSA=True,
        threshold_sequence_frac_gaps=0.5,
        threshold_focus_cols_frac_gaps=0.5)
    if data.seq_len != ckpt["encoder_parameters"]["seq_len"]:
        raise RuntimeError(f"MSA 清洗后 {data.seq_len} 列 != checkpoint "
                           f"{ckpt['encoder_parameters']['seq_len']} 列(阈值不符?)")

    model = VAE_model.VAE_model(
        model_name="pbatase_sweep",
        data=data,
        encoder_parameters=ckpt["encoder_parameters"],
        decoder_parameters=ckpt["decoder_parameters"],
        random_seed=42)
    model.load_state_dict(ckpt["model_state_dict"])
    model = model.to(model.device).eval()

    # 单点突变 ΔELBO: ELBO(mut) − ELBO(wt); EVE 官方语义(越高越兼容)。
    # wt 中心残基 token 序列(MSA_processing 的 one_hot: data.X_focus 列序对齐)
    scores = {}
    with torch.no_grad():
        wt_tokens = data.X_focus[0].to(model.device)   # (seq_len,) 残基索引
        alphabet = "ACDEFGHIKLMNPQRSTVWY"
        aa_to_idx = {c: i for i, c in enumerate(alphabet)}
        # EVE 内部字母表序(data_utils MSA_processing 用 aa_to_idx 一致)
        wt_idx = data.aa_to_idx[int(wt_tokens[0])] if hasattr(data, "aa_to_idx") else None
        # 稳妥: 直接用 data.X_focus 的 one_hot 形状走 elbo
        x_wt = data.X_focus[0:1].to(model.device).float()
        elbo_wt = model.elbo_neurons_deterministic(x_wt, S=10) \
            if hasattr(model, "elbo_neurons_deterministic") else None
        if elbo_wt is None:
            raise RuntimeError("VAE_model 无 elbo_neurons_deterministic(EVE 版本不符?)")
        elbo_wt = float(elbo_wt.mean())
        for v in VAR:
            x = x_wt.clone()
            col = data.uniprot_focus_col_to_focus_idx[v["site"]]  # 1-based → focus 列
            x[0, col, :] = 0
            x[0, col, aa_to_idx[v["to"]]] = 1.0
            elbo_m = float(model.elbo_neurons_deterministic(x, S=10).mean())
            scores[v["id"]] = round(elbo_m - elbo_wt, 4)
    return scores


if __name__ == "__main__":
    _t0 = time.time()
    try:
        _r = run()
        print(json.dumps({"scores": _r, "elapsed_s": round(time.time() - _t0, 1)}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": "{}: {}".format(type(e).__name__, str(e)[:300]),
                          "elapsed_s": round(time.time() - _t0, 1)}))
