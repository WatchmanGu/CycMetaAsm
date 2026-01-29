version 1.0

task classify_bins {
  input {
    Array[File] bins
    Array[File]? scMAGs
    File skani_database
    Int threads = 10
    String assembler = "metaflye"
    String tool = "skani"
    Float ass2ref = 0.5
  }

  command <<<
    set -euo pipefail

    mkdir -p work/all_bins

    # Link bins
    for f in ~{sep=' ' bins}; do ln -s "$f" work/all_bins/; done
    # Link scMAGs if provided
    if [[ ~{length(select_first([scMAGs, []]))} -gt 0 ]]; then
      for f in ~{sep=' ' select_first([scMAGs, []])}; do ln -s "$f" work/all_bins/; done
    fi

    cycmetaasm classify work/all_bins work \
      --assembler ~{assembler} \
      --threads ~{threads} \
      --database ~{skani_database} \
      --metadata ~{skani_database}/metadata.tsv \
      --tool ~{tool} \
      --ass2ref ~{ass2ref}
  >>>

  output {
    File classify_result = "work/classify/~{assembler}/classify_result_deduplicated.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.0.0"
    cpu: threads + 2
    memory: "48G"
  }
}
