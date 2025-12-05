version 1.0

task assemble_and_select {
  input {
    File clean_fastq
    Int threads = 16
    String assembler = "metaflye"
    Boolean polish
    File? short_reads1
    File? short_reads2
    File checkm2_db_path
  }

  command <<<
    set -euo pipefail

    mkdir -p work
    #Workaround for Python multiprocessing, fixes "AF_UNIX path too long"
    mkdir -p /tmp
    export TMPDIR="/tmp"

    cycmetaasm assemble ~{clean_fastq} work \
      --assembler ~{assembler} \
      --threads ~{threads} \
      ~{if polish then "--polish" else ""} \
      ~{if defined(short_reads1) then "--short-reads1" else ""} ~{short_reads1} \
      ~{if defined(short_reads2) then "--short-reads2" else ""} ~{short_reads2} \
      --checkm2-db ~{checkm2_db_path}
      cp -L ~{if polish then "work/Assembly/~{assembler}/polish/genome.nextpolish.fasta" else "work/Assembly/~{assembler}/assembly.fasta"} assembly.fasta
  >>>

  output {
    File assembly_fasta = "assembly.fasta"
    # File assembly_info = "work/Assembly/~{assembler}/assembly_info.tsv"
    File tobe_binned_fasta = "work/to_be_binned.fasta"
    Array[File] scMAGs = glob("work/scMAGs/*.fa")
    File scMAGs_info = "work/scMAGs/scMAGs_info.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.0.0"
    cpu: threads + 2
    memory: "80G"
  }
}
