version 1.0

task bin_and_checkm2 {
  input {
    File raw_contigs
    File reads_fastq
    Int threads = 10
    String assembler = "metaflye"
    String sequencing_tech = "CycloneSEQ"
    String binning_mode = "global"
    File? checkm2_db_path
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
      ~{if defined(checkm2_db_path) then "--checkm2-db " + checkm2_db_path else ""}
    
    # If checkm2_db_path is not provided, create an empty quality report
    if [[ ~{defined(checkm2_db_path)} == "false" ]]; then
      mkdir -p work/checkm2
      echo -e "Name\tCompleteness\tContamination\tContig_N50\tTotal_Contigs\tGenome_Size" > work/checkm2/quality_report.tsv
    fi
  >>>

  output {
    Array[File] bins = glob("work/output_bins/SemiBin_*.fa")
    File quality_report = "work/checkm2/quality_report.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.0.0"
    cpu: threads + 2
    memory: "80G"
  }
}
