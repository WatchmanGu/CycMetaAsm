version 1.0

task bin_and_checkm2 {
  input {
    File raw_contigs
    File reads_fastq
    Int threads = 16
    String assembler = "metaflye"
    String sequencing_tech = "CycloneSEQ"
    String binning_mode = "global"
    File checkm2_db_path
  }

  command <<<
    set -euo pipefail

    mkdir -p work
    mkdir -p /tmp
    export TMPDIR="/tmp"

    cycmetaasm bin ~{raw_contigs} ~{reads_fastq} work \
      --assembler ~{assembler} \
      --threads ~{threads} \
      --sequencing-tech ~{sequencing_tech} \
      --binning-model ~{binning_mode} \
      --checkm2-db ~{checkm2_db_path}
  >>>

  output {
    Array[File] bins = glob("work/Binning/~{assembler}/output_bins/SemiBin_*.fa")
    File quality_report = "work/evaluation/~{assembler}_bins/checkm2/quality_report.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.0.0"
    cpu: threads + 2
    memory: "80G"
  }
}
