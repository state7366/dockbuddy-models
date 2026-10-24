import click
import torch
from Bio import SeqIO
import esm
from esm.pretrained import load_model_and_alphabet_core


@click.command()
@click.option("--fasta_file", required=True, type=str)
@click.option("--saved_folder", required=True, type=str)
def main(fasta_file, saved_folder):
    with torch.no_grad():
        # 坑1: torch.hub.load 会从 github 下载(实例不通)。
        # 坑2: load_model_and_alphabet_local 对 esm2 强制加载 contact-regression.pt
        # (实例无该文件) → 直接加载主权重 + load_model_and_alphabet_core(regression=None,
        # 只 warning 不加载 contact; embedding 不需要 contact head)
        model_location = "/home/ubuntu/dockbuddy/models/esm2/esm2_t33_650M_UR50D.pt"
        model_data = torch.load(model_location, map_location="cpu")
        model, alphabet = load_model_and_alphabet_core("esm2_t33_650M_UR50D", model_data, None)
        model = model.eval().to("cpu")

        batch_converter = alphabet.get_batch_converter()
        data = [("protein", str(list(SeqIO.parse(fasta_file, "fasta"))[0].seq))]
        batch_labels, batch_strs, batch_tokens = batch_converter(data)

        result = model(batch_tokens.to("cpu"), repr_layers=[33], return_contacts=False)
        representations = result["representations"][33][0, 1:-1, :]
        torch.save(representations.detach().cpu().clone(), f"{saved_folder}/esm2.pt")


if __name__ == "__main__":
    main()
