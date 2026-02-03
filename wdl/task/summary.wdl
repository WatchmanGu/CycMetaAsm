version 1.0

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
    docker: "cycmetaasm:v1.0.0"
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
    docker: "cycloneseq-report:v1.4.0"
    cpu: threads
    memory: "16G"
  }
}
