#!/usr/bin/env bash

set -Eeuo pipefail

#######################################################################
# conda environment
#######################################################################

__conda_setup="$('conda' 'shell.bash' 'hook' 2> /dev/null)"
eval "$__conda_setup"
unset __conda_setup

conda activate geostab

#######################################################################
# software
#######################################################################

export GEOSTAB_DIR=$(dirname $(realpath $0))
# FoldX 二进制解析(2026-10-15 补丁, 自包含 —— 不再依赖部署脚本 sed 改写路径):
#   ① 仓库自带 software/foldx/foldx(上游默认布局);
#   ② $FOLDX_BIN(部署注入: setup_v9.sh step3 落位 models/foldx/foldx_20261231,
#      并写 /etc/profile.d/dockbuddy.sh);
#   ③ PATH 中的 foldx(setup_v9.sh step3 软链 /usr/local/bin/foldx);
#   ④ 部署默认路径兜底。
# 另注意: FoldX RepairPDB/BuildModel 从 **当前工作目录** 读 rotabase.txt, 而
# rotabase.txt 与 foldx 二进制同目录 → 下方两处调用都包了
# `(cd "$(dirname "${software_foldx}")" && ...)` 子 shell, 保证 FoldX 找到
# rotabase.txt(否则报 can't open rotabase.txt)。
software_foldx=${GEOSTAB_DIR}/software/foldx/foldx
if [ ! -x "$software_foldx" ]; then
  if [ -n "${FOLDX_BIN:-}" ] && [ -x "${FOLDX_BIN}" ]; then
    software_foldx="${FOLDX_BIN}"
  elif command -v foldx >/dev/null 2>&1; then
    software_foldx="$(command -v foldx)"
  else
    software_foldx=/home/ubuntu/dockbuddy/models/foldx/foldx_20261231
  fi
fi

#######################################################################
# pasre parameters
#######################################################################

help() {
    echo -e "Usage:\n"
    echo -e "bash run.sh [-m METRIC] [-v VERSION] [-o FOLDER]\n"
    echo -e "Description:\n"
    echo -e " \e[1;31m-m\e[0m choose one of the two metrics (fitness or ddGdTm) (e.g. -m fitness / -m ddGdTm)"
    echo -e " \e[1;31m-v\e[0m choose one of the two versions (Seq or threeD) (e.g. -v Seq / -v threeD)"
    echo -e " \e[1;31m-o\e[0m output folder (e.g. -o ./example_3D)"
    echo -e "\e[1;31mAll parameters must be set!\e[0m"
    exit 1
}

# check the number of parameters
if [ $# -ne 6 ]; then
    echo -e "\e[1;31mThe number of parameters is wrong!\e[0m"
    help
fi

# check the validity of parameters
while getopts 'm:v:o:' PARAMETER
do
    case ${PARAMETER} in
        m)
        metric=${OPTARG};;
        v)
        version=${OPTARG};;
        o)
        folder=$(realpath -e ${OPTARG});;
        ?)
        help;;
    esac
done

shift "$(($OPTIND - 1))"

#######################################################################
# run
#######################################################################

echo -e "Metric: \e[1;31m${metric}\e[0m"
echo -e "Version: \e[1;31m${version}\e[0m"
echo -e "Output folder: \e[1;31m${folder}\e[0m"

wt_folder=${folder}/wt_data
mut_folder=${folder}/mut_data

# generate wt features
# 串行执行: 每个大模型进程峰值 RSS 实测 ~9.7G(anon-rss), 机型 4C19G,
# 任何 >=2 个大模型(esm1v/esm2)并行都会触发 OOM killer(见 syslog
# "Out of memory: Killed process"), 且无参 wait 在 set -e 下会静默吞掉
# 后台失败 → ensemble_ddGdTm.py 报莫名的 FileNotFoundError。串行后
# set -e 自然恢复错误传播, 失败立刻暴露。
if [ ! -s ${wt_folder}/fixed_embedding.pt ]; then
    echo -e "run \e[1;31mwt fixed embedding\e[0m"
    python ${GEOSTAB_DIR}/generate_features/fixed_embedding.py --fasta_file ${wt_folder}/result.fasta --saved_folder ${wt_folder}
fi

if [ ! -s ${wt_folder}/esm2.pt ]; then
    echo -e "run \e[1;31mwt esm2 embedding\e[0m"
    python ${GEOSTAB_DIR}/generate_features/esm2_embedding.py --fasta_file ${wt_folder}/result.fasta --saved_folder ${wt_folder}
fi

for i in 1 2 3 4 5; do
    if [ ! -s ${wt_folder}/esm1v-${i}.pt ]; then
        echo -e "run \e[1;31mwt esm1v-${i} logits\e[0m"
        python ${GEOSTAB_DIR}/generate_features/esm1v_logits.py --model_index ${i} --fasta_file ${wt_folder}/result.fasta --saved_folder ${wt_folder}
    fi
done

# use AlphaFold2 to generate 3D structure
if [ ${version} == 'Seq' ]; then
    if [ ! -s ${wt_folder}/result.a3m ]; then
        echo -e "run \e[1;31mwt MSA\e[0m"
        /data3/alphafold/hhsuite/bin/hhblits -i ${wt_folder}/result.fasta -oa3m ${wt_folder}/result.a3m -cpu 20 -d /data4/database/UniRef30_2021_03/UniRef30_2021_03 -d /data4/database/bfd/bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt -o /dev/null -n 3 -e 0.001 -maxfilt 100000 -min_prefilter_hits 1000 -id 99 -diff 0 -cov 25 -mact 0.35 -realign_max 100000 -premerge 3 -v 1 -neffmax 20 -maxseq 1000000 -maxmem 64
    fi

    if [ ! -s ${wt_folder}/unrelaxed.pdb ]; then
        echo -e "run \e[1;31mwt AlphaFold2 unrelax\e[0m"
        conda activate alphafold
        CUDA_VISIBLE_DEVICES=7 python /data3/alphafold/run_alphafold_msa.py --fasta_path ${wt_folder}/result.fasta --msa_path ${wt_folder}/result.a3m --output_dir ${wt_folder} || CUDA_VISIBLE_DEVICES="" python /data3/alphafold/run_alphafold_msa.py --fasta_path ${wt_folder}/result.fasta --msa_path ${wt_folder}/result.a3m --output_dir ${wt_folder}
    fi

    if [ ! -s ${wt_folder}/relaxed.pdb ]; then
        echo -e "run \e[1;31mwt AlphaFold2 relax\e[0m"
        conda activate alphafold
        CUDA_VISIBLE_DEVICES=7 python /data3/alphafold/run_alphafold_only_relax.py --output_dir ${wt_folder} || CUDA_VISIBLE_DEVICES="" python /data3/alphafold/run_alphafold_only_relax.py --output_dir ${wt_folder}
        conda activate geostab
        pdb_fixinsert ${wt_folder}/relaxed.pdb | pdb_reres -0 | pdb_chain -A | pdb_tidy > ${wt_folder}/tmp.pdb
        mv ${wt_folder}/tmp.pdb ${wt_folder}/relaxed.pdb
    fi
fi

if [ ! -s ${wt_folder}/relaxed_repair.pdb ]; then
    echo -e "run \e[1;31mwt FoldX\e[0m"
    mkdir -p ${wt_folder}/foldx_tmp
    # FoldX RepairPDB/BuildModel 从 **当前工作目录** 读 rotabase.txt; 而 rotabase.txt 与
    # foldx 二进制同目录(models/foldx/)。--pdb-dir/--output-dir 已是绝对路径, 故用子 shell
    # cd 到 foldx 二进制所在目录再跑, 让 FoldX 找到 rotabase.txt(否则报 can't open rotabase.txt)。
    (cd "$(dirname "${software_foldx}")" && ${software_foldx} --command=RepairPDB --pdb=relaxed.pdb --pdb-dir=${wt_folder} --output-dir=${wt_folder}/foldx_tmp)
    cp ${wt_folder}/foldx_tmp/relaxed_Repair.pdb ${wt_folder}/relaxed_repair.pdb
fi

if [ ! -s ${wt_folder}/coordinate.pt ]; then
    echo -e "run \e[1;31mwt coordinate\e[0m"
    python ${GEOSTAB_DIR}/generate_features/coordinate.py --pdb_file ${wt_folder}/relaxed_repair.pdb --saved_folder ${wt_folder}
fi

if [ ! -s ${wt_folder}/pair.pt ]; then
    echo -e "run \e[1;31mwt pair\e[0m"
    python ${GEOSTAB_DIR}/generate_features/pair.py --coordinate_file ${wt_folder}/coordinate.pt --saved_folder ${wt_folder}
fi

# generate fitness features and predict fitness
if [ ${metric} == 'fitness' ]; then
    echo -e "run \e[1;31m${version} ${metric}\e[0m"
    if [ ${version} == 'Seq' ]; then
        python ${GEOSTAB_DIR}/generate_features/ensemble_fitness.py --af2_pickle_file ${wt_folder}/result.pkl --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_fitness_Seq/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
    else
        python ${GEOSTAB_DIR}/generate_features/ensemble_fitness.py --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_fitness_3D/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
    fi
else

    # generate mut features
    if [ ! -s ${mut_folder}/fixed_embedding.pt ]; then
        echo -e "run \e[1;31mmut fixed embedding\e[0m"
        python ${GEOSTAB_DIR}/generate_features/fixed_embedding.py --fasta_file ${mut_folder}/result.fasta --saved_folder ${mut_folder} &
    fi

    if [ ! -s ${mut_folder}/esm2.pt ]; then
        echo -e "run \e[1;31mmut esm2 embedding\e[0m"
        python ${GEOSTAB_DIR}/generate_features/esm2_embedding.py --fasta_file ${mut_folder}/result.fasta --saved_folder ${mut_folder} &
    fi

    wait

    if [ ! -s ${mut_folder}/relaxed_repair.pdb ]; then
        echo -e "run \e[1;31mmut FoldX\e[0m"
        mkdir -p ${mut_folder}/foldx_tmp
        (cd "$(dirname "${software_foldx}")" && ${software_foldx} --command=BuildModel --pdb=relaxed_repair.pdb --pdb-dir=${wt_folder} --mutant-file=${mut_folder}/individual_list.txt --numberOfRuns=3 --output-dir=${mut_folder}/foldx_tmp)
        cp ${mut_folder}/foldx_tmp/relaxed_repair_1_2.pdb ${mut_folder}/relaxed_repair.pdb
    fi

    if [ ! -s ${mut_folder}/coordinate.pt ]; then
        echo -e "run \e[1;31mmut coordinate\e[0m"
        python ${GEOSTAB_DIR}/generate_features/coordinate.py --pdb_file ${mut_folder}/relaxed_repair.pdb --saved_folder ${mut_folder}
    fi
    
    if [ ! -s ${mut_folder}/pair.pt ]; then
        echo -e "run \e[1;31mmut pair\e[0m"
        python ${GEOSTAB_DIR}/generate_features/pair.py --coordinate_file ${mut_folder}/coordinate.pt --saved_folder ${mut_folder}
    fi

    # generate ΔΔG/ΔTm features and predict ΔΔG/ΔTm
    echo -e "run \e[1;31m${version} ${metric}\e[0m"
    if [ ${version} == 'Seq' ]; then
        python ${GEOSTAB_DIR}/generate_features/ensemble_ddGdTm.py --af2_pickle_file ${wt_folder}/result.pkl --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_ddG_Seq/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_dTm_Seq/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_fitness_Seq/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
    else
        python ${GEOSTAB_DIR}/generate_features/ensemble_ddGdTm.py --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_ddG_3D/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_dTm_3D/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
        python ${GEOSTAB_DIR}/model_fitness_3D/predict.py --ensemble_feature ${folder}/ensemble.pt --saved_folder ${folder}
    fi
fi
