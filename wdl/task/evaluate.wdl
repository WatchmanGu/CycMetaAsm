version 1.0

task evaluate_assembly {
  input {
    File assembly_fasta
    Int threads = 10
    String assembler = "metaflye"
    File? database_root
    String? reference_fasta
    File? assembly_info
  }

  command <<<_
    set -euo pipefail

    mkdir -p work

    EVAL_ARGS="--assembler ~{assembler} --threads ~{threads}"
    if [[ -n "~{select_first([database_root, ""]) }" ]]; then
      EVAL_ARGS="$EVAL_ARGS --database ~{select_first([database_root, ""]) }"
    fi
    if [[ -n "~{select_first([reference_fasta, ""]) }" ]]; then
      EVAL_ARGS="$EVAL_ARGS --reference ~{select_first([reference_fasta, ""]) }"
    fi
    if [[ -n "~{select_first([assembly_info, ""]) }" ]]; then
      EVAL_ARGS="$EVAL_ARGS --assembly-info ~{select_first([assembly_info, ""]) }"
    fi

    cycmetaasm evaluate ~{assembly_fasta} work $EVAL_ARGS

    cp work/evaluation/~{assembler}/assembly_contigs_info.tsv assembly_contigs_info.tsv
  _>>>

  output {
    File assembly_contigs_info = "assembly_contigs_info.tsv"
  }

  runtime {
    cpu: threads
    memory: "8G"
  }
}
