import click
import torch
from Bio import SeqIO
import esm


@click.command()
@click.option("--model_index", required=True, type=str)
@click.option("--fasta_file", required=True, type=str)
@click.option("--saved_folder", required=True, type=str)
def main(model_index, fasta_file, saved_folder):
    seq = str(list(SeqIO.parse(fasta_file, "fasta"))[0].seq)
    with torch.no_grad():
        # 坑: torch.hub.load 会从 github 下载(实例不通); 改用本地 fair-esm 权重
        # ESM-1v 权重由 esm1v model.json 拉到 $MODELS_ROOT/esm1v/(默认
        # /home/ubuntu/dockbuddy/models/esm1v/), 与 setup_v9.sh 落位口径一致; 支持 ESM1V_DIR 覆盖。
        # 坑2: load_model_and_alphabet_local 对 esm1v 也强制加载 contact-regression.pt
        # (实例无该文件) → 直接加载主权重 + load_model_and_alphabet_core(regression=None,
        # 只 warning 不加载 contact; logits 不需要 contact head)
        import os
        from esm.pretrained import load_model_and_alphabet_core
        _esm1v_dir = os.environ.get("ESM1V_DIR", "/home/ubuntu/dockbuddy/models/esm1v")
        _model_path = f"{_esm1v_dir}/esm1v_t33_650M_UR90S_{model_index}.pt"
        model_data = torch.load(_model_path, map_location="cpu")
        model_name = os.path.splitext(os.path.basename(_model_path))[0]
        model, alphabet = load_model_and_alphabet_core(model_name, model_data, None)
        model = model.eval().to("cpu")

        batch_converter = alphabet.get_batch_converter()
        data = [("protein", seq)]
        batch_labels, batch_strs, batch_tokens = batch_converter(data)

        token_probs = torch.log_softmax(model(batch_tokens)["logits"], dim=-1)
        logits_33 = token_probs[0, 1:-1, :].detach().cpu().clone()

        # logits 33 dim -> 20 dim
        amino_acid_list = list("ARNDCQEGHILKMFPSTWYV")
        esm1v_amino_acid_dict = {}
        for i in amino_acid_list:
            esm1v_amino_acid_dict[i] = alphabet.get_idx(i)

        logits_20 = torch.zeros((logits_33.shape[0], 20))
        for wt_pos, wt_amino_acid in enumerate(seq):
            for mut_pos, mut_amino_acid in enumerate(amino_acid_list):
                logits_20[wt_pos, mut_pos] = logits_33[wt_pos, esm1v_amino_acid_dict[mut_amino_acid]] - logits_33[wt_pos, esm1v_amino_acid_dict[wt_amino_acid]]

        torch.save(logits_20.detach().cpu().clone(), f"{saved_folder}/esm1v-{model_index}.pt")


if __name__ == "__main__":
    main()
