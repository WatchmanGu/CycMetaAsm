version 1.0

# Standalone DCS workflow generated from wdl/workflow.wdl and imported task WDLs.
# DCS accepts a single WDL file, so all called tasks are defined in this file.

task preprocess {
  input {
    File input_fastq
    Int threads = 10
    String sequencing_tech = "CycloneSEQ"
    Int min_length = 1000
    Int min_quality = 7
    File? host_reference
    Float? downsample
  }

  command <<<
    set -euo pipefail

    mkdir -p work

    #
    # Handle downsample logic in bash
    #
    DS_FLAG=""
    if [[ ~{defined(downsample)} == "true" ]]; then
        ds="~{downsample}"

        # Case 1: Value < 0.1: only warn, do not apply downsampling
        awk_res=$(awk -v v="$ds" 'BEGIN {if (v < 0.1) print "lt"; else print "ge"}')
        if [[ "$awk_res" == "lt" ]]; then
            echo "[WARNING] The sampled data volume is too small; assembly may fail!" >&2
            # Do NOT enable downsampling
        else
            # Case 2: Value == 0: disable downsampling
            if awk -v v="$ds" 'BEGIN {exit !(v == 0)}'; then
                echo "[INFO] Downsample value is 0; downsampling disabled."
            else
                # Case 3: Normal downsampling
                DS_FLAG="${ds}G"
            fi
        fi
    fi
    if [[ -n "$DS_FLAG" ]]; then
        echo "[INFO] Downsampling enabled: target data volume = $DS_FLAG"
        cycmetaasm preprocess ~{input_fastq} work \
        --threads ~{threads} \
        --sequencing-tech ~{sequencing_tech} \
        --min-length ~{min_length} \
        --min-quality ~{min_quality} \
        ~{if defined(host_reference) then "--host-reference " + host_reference else ""} \
        --downsample "${DS_FLAG}"
    else
        echo "[INFO] Downsampling disabled."
        cycmetaasm preprocess ~{input_fastq} work \
        --threads ~{threads} \
        --sequencing-tech ~{sequencing_tech} \
        --min-length ~{min_length} \
        --min-quality ~{min_quality} \
        ~{if defined(host_reference) then "--host-reference " + host_reference else ""}
    fi

    cp ~{if defined(host_reference) then "work/remove_host/host_removed.fastq.gz" else "work/qc/filtered.fastq.gz"} clean.fastq.gz
  >>>

  output {
    File clean_fastq = "clean.fastq.gz"
  }

  runtime {
    docker: "cycmetaasm:v1.1.0"
    cpu: threads + 2
    memory: "80G"
  }
}

task RunRosa{
    input {
        File fastq_file
        String sample_id
    }

    command <<<
        set -euo pipefail
        echo "Running Rosa for quality control..."
        rosa \
            -i ~{fastq_file} \
            --sample-name ~{sample_id} \
            --seed 9999 \
            --sample-size 100000 \
            -o result \
            -t 4

        if [ ! -f result/report.html ]; then
            echo "Rosa report not found!"
            exit 1
        fi
        mv result/report.html result/~{sample_id}_QC_report.html
        zip -r ~{sample_id}_QC_results.zip result/
        echo "Rosa QC completed."
    >>>

    output {
        File rosa_results_zip = "~{sample_id}_QC_results.zip"
        Array[File] rosa_results = [
            "result/fastx_analyses/figures/read_length_distribution.png",
            "result/fastx_analyses/figures/read_quality_distribution.png",
            "result/fastx_analyses/figures/cumulative_read_length.png",
            "result/fastx_analyses/figures/read_length_vs_quality.png",
            "result/fastx_analyses/results/reference-free_QC_results_summary.tsv"
        ]
    }

    runtime {
        docker: "cycmetaasm:v1.1.0"
        cpu: 10
        memory: 32 + "GB"
    }
}

task assemble_and_select {
  input {
    File clean_fastq
    Int threads = 10
    String assembler = "myloasm"
    Boolean polish
    File? short_reads1
    File? short_reads2
    File? checkm2_db_path
  }

  command <<<
    set -euo pipefail

    mkdir -p work
    # Workaround for Python multiprocessing, fixes "AF_UNIX path too long"
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
    docker: "cycmetaasm:v1.1.0"
    cpu: threads + 2
    memory: "80G"
  }
}

task bin_and_checkm2 {
  input {
    File raw_contigs
    File reads_fastq
    Int threads = 10
    String assembler = "myloasm"
    String binner = "lorbin"
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
      --binner ~{binner} \
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
    Array[File] bins = glob("work/output_bins/*.fa")
    File quality_report = "work/checkm2/quality_report.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.1.0"
    cpu: threads + 2
    memory: "80G"
  }
}

task classify_bins {
  input {
    Array[File] bins
    Array[File]? scMAGs
    File skani_database
    Int threads = 10
    String assembler = "myloasm"
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
    File classify_result = "work/classify_result_deduplicated.tsv"
  }

  runtime {
    docker: "cycmetaasm:v1.1.0"
    cpu: threads + 2
    memory: "48G"
  }
}

task summarize_results {
  input {
    Array[File]? scMAGs
    File? scMAGs_info
    Array[File] bins
    File bins_quality_report
    File? classification_tsv
    File? fastq
    Int threads = 10
  }

  # Turn optional Array[File]? into a concrete Array[File] (possibly empty)
  Array[File] scmags_list = select_first([scMAGs, []])

  command <<<
    set -euo pipefail

    mkdir -p all_mags
    # Only copy scMAGs if we actually have any
    if [[ ~{length(scmags_list)} -gt 0 ]]; then
      cp -L ~{sep=' ' scmags_list} all_mags/
    fi

    cp -L ~{sep=' ' bins} all_mags/
    mkdir -p summary
    touch summary/taxonomic_abundance.html summary/rank_completeness_contamination.png summary/contig_n50_violin.png
    cycmetaasm summarize ~{bins_quality_report} \
      summary \
      ~{if defined(classification_tsv) then "--classification " + classification_tsv else ""} \
      --mag-path all_mags \
      ~{if defined(scMAGs_info) then "--scmag-info " + scMAGs_info else ""} \
      ~{if defined(fastq) then "--fastq-file " + fastq else ""} \
      --threads ~{threads}
  >>>

  output {
    File summary_tsv = "summary/summary.tsv"
    File top_summary_tsv = "summary/top_ranked_mag_summary.tsv"
    File passed_mags = "summary/passed_quality_mags"
    File low_quality_mags = "summary/low_quality_mags"
    File mag_quality_table = "summary/quality_stats.tsv"
    File taxonomic_abundance_html = "summary/taxonomic_abundance.html"
    File quality_rank_img = "summary/rank_completeness_contamination.png"
    File contig_n50_img = "summary/contig_n50_violin.png"
  }

  runtime {
    docker: "cycmetaasm:v1.1.0"
    cpu: threads + 2
    memory: "48G"
  }
}

task make_report {
  input {
    String sample_id
    File raw_rosa_results_zip
    File clean_rosa_results_zip
    Array[File] raw_rosa_results
    Array[File] clean_rosa_results
    File summary_tsv
    File top_summary_tsv
    File passed_mags
    File low_quality_mags
    File mag_quality_table
    File taxonomic_abundance_html
    File quality_rank_img
    File contig_n50_img
    File report_config
    Int threads
  }

  command <<<
    set -euo pipefail
    echo "Generating final report..."
    mkdir -p results/raw_rosa_results results/clean_rosa_results
    cp ~{sep=' ' raw_rosa_results} results/raw_rosa_results/
    cp ~{sep=' ' clean_rosa_results} results/clean_rosa_results/
    cp -r ~{raw_rosa_results_zip} ~{clean_rosa_results_zip} ~{summary_tsv} ~{top_summary_tsv} ~{passed_mags} ~{low_quality_mags} ~{mag_quality_table} ~{taxonomic_abundance_html} ~{quality_rank_img} ~{contig_n50_img} results/
    cycloneseq-report ~{report_config} \
        -o results/~{sample_id}_CycMetaAsm_Report.html \
        -w results/
    echo "Final report generated."
    rm -r results/clean_rosa_results/ results/raw_rosa_results/
    mv results ~{sample_id}_CycMetaAsm_Results
    zip -r ~{sample_id}_CycMetaAsm_Results.zip ~{sample_id}_CycMetaAsm_Results/
    echo "Results zipped."
    paste -d "\t" <(echo -e "Sample_id\n~{sample_id}") ~{mag_quality_table} > summary.txt
  >>>

  output {
    File report_html = "~{sample_id}_CycMetaAsm_Results/~{sample_id}_CycMetaAsm_Report.html"
    File results_zip = "~{sample_id}_CycMetaAsm_Results.zip"
    File job_summary = "summary.txt"
  }

  runtime {
    docker: "cycmetaasm:v1.1.0"
    cpu: threads
    memory: "16G"
  }
}

workflow CycMetaAsmWorkflow {
  input {
    File report_config_yaml
    String sample_id
    File input_fastq
    Int threads = 40
    String sequencing_tech = "CycloneSEQ"
    String assembler = "myloasm"
    String binner = "lorbin"
    File? checkm2_db_path
    File? skani_database
    Int min_length = 1000
    Int min_quality = 7
    Boolean polish = false
    File? short_reads1
    File? short_reads2
    File? host_reference
    Float? downsample
    String binning_mode = "global"
    String classify_tool = "skani"
    Float classify_ass2ref = 0.5
  }

  call RunRosa as raw_rosa_step {
    input:
      fastq_file = input_fastq,
      sample_id = "raw"
  }

  call preprocess as preprocess_step {
    input:
      input_fastq = input_fastq,
      threads = threads,
      sequencing_tech = sequencing_tech,
      min_length = min_length,
      min_quality = min_quality,
      host_reference = host_reference,
      downsample = downsample
  }

  call RunRosa as clean_rosa_step {
    input:
      fastq_file = preprocess_step.clean_fastq,
      sample_id = "clean"
  }

  call assemble_and_select as assemble_step {
    input:
      clean_fastq = preprocess_step.clean_fastq,
      threads = threads,
      assembler = assembler,
      polish = polish,
      short_reads1 = short_reads1,
      short_reads2 = short_reads2,
      checkm2_db_path = checkm2_db_path
  }

  call bin_and_checkm2 as bin_step {
    input:
      raw_contigs = assemble_step.tobe_binned_fasta,
      reads_fastq = preprocess_step.clean_fastq,
      threads = threads,
      assembler = assembler,
      binner = binner,
      sequencing_tech = sequencing_tech,
      binning_mode = binning_mode,
      checkm2_db_path = checkm2_db_path
  }

  # Optional classification: only run if skani_database is provided
  if (defined(skani_database)) {
    call classify_bins as classify_step {
      input:
        bins = bin_step.bins,
        scMAGs = assemble_step.scMAGs,
        skani_database = select_first([skani_database]),
        threads = threads,
        assembler = assembler,
        tool = classify_tool,
        ass2ref = classify_ass2ref
    }
  }

  # Always summarize results; use separate aliases
  call summarize_results as summary_step {
    input:
      scMAGs = assemble_step.scMAGs,
      scMAGs_info = assemble_step.scMAGs_info,
      bins = bin_step.bins,
      bins_quality_report = bin_step.quality_report,
      classification_tsv = classify_step.classify_result,
      fastq = preprocess_step.clean_fastq,
      threads = threads
  }

  # Make a report, taxonomic information optional
  call make_report as report_step {
    input:
      sample_id = sample_id,
      raw_rosa_results_zip = raw_rosa_step.rosa_results_zip,
      clean_rosa_results_zip = clean_rosa_step.rosa_results_zip,
      raw_rosa_results = raw_rosa_step.rosa_results,
      clean_rosa_results = clean_rosa_step.rosa_results,
      summary_tsv = summary_step.summary_tsv,
      top_summary_tsv = summary_step.top_summary_tsv,
      passed_mags = summary_step.passed_mags,
      low_quality_mags = summary_step.low_quality_mags,
      mag_quality_table = summary_step.mag_quality_table,
      taxonomic_abundance_html = summary_step.taxonomic_abundance_html,
      quality_rank_img = summary_step.quality_rank_img,
      contig_n50_img = summary_step.contig_n50_img,
      report_config = report_config_yaml,
      threads = 4
  }

  output {
    File report_html = report_step.report_html
    File report_zip = report_step.results_zip
    File job_summary = report_step.job_summary
  }
}
