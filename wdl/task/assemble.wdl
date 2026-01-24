version 1.0

task assemble_and_select {
  input {
    File clean_fastq
    Int threads = 10
    String assembler = "metaflye"
    Boolean polish
    File? short_reads1
    File? short_reads2
    File? checkm2_db_path
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
      ~{if defined(checkm2_db_path) then "--checkm2-db " + checkm2_db_path else ""}

    # Copy the final assembly (polished or raw)
    cp -L ~{if polish then "work/polish/genome.nextpolish.fasta" else "work/assembly.fasta"} assembly.fasta

    # Handle output paths based on whether CheckM2 db was provided
    if [[ ~{defined(checkm2_db_path)} == "true" ]]; then
      # CheckM2 processing creates subset_contigs directory
      if [ -f work/subset_contigs/to_be_binned.fasta ]; then
        cp -L work/subset_contigs/to_be_binned.fasta to_be_binned.fasta
      else
        # Fallback if directory structure is different
        cp -L assembly.fasta to_be_binned.fasta
      fi
      # Create scMAGs directory link or copy
      if [ -d work/subset_contigs/scMAGs ]; then
        cp -rL work/subset_contigs/scMAGs work/scMAGs_output
      else
        mkdir -p work/scMAGs_output
      fi
      # Ensure scMAGs_info.tsv exists
      if [ ! -f work/subset_contigs/scMAGs/scMAGs_info.tsv ] && [ ! -f work/scMAGs_output/scMAGs_info.tsv ]; then
        echo -e "Contig\tLength\tCompleteness\tContamination" > work/scMAGs_output/scMAGs_info.tsv
      elif [ -f work/subset_contigs/scMAGs/scMAGs_info.tsv ]; then
        cp work/subset_contigs/scMAGs/scMAGs_info.tsv work/scMAGs_output/scMAGs_info.tsv
      fi
    else
      # No CheckM2 db provided - all contigs go to binning
      cp -L assembly.fasta to_be_binned.fasta
      mkdir -p work/scMAGs_output
      echo -e "Contig\tLength\tCompleteness\tContamination" > work/scMAGs_output/scMAGs_info.tsv
    fi
  >>>

  output {
    File assembly_fasta = "assembly.fasta"
    File tobe_binned_fasta = "to_be_binned.fasta"
    Array[File] scMAGs = glob("work/scMAGs_output/*.fa")
    File scMAGs_info = "work/scMAGs_output/scMAGs_info.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.0.0"
    cpu: threads + 2
    memory: "80G"
  }
}
