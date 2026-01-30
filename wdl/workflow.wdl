version 1.0

import "task/preprocess.wdl" as PP
import "task/assemble.wdl" as AS
import "task/bin.wdl" as BN
import "task/classify.wdl" as CL
import "task/summary.wdl" as SM

workflow CycMetaAsmWorkflow {
  input {
    File report_config_yaml
    String sample_id
    File input_fastq
    Int threads = 40
    String sequencing_tech = "CycloneSEQ"
    String assembler = "metaflye"
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

  call PP.RunRosa as raw_rosa_step {
    input:
      fastq_file = input_fastq,
      sample_id = "raw"
  }

  call PP.preprocess as preprocess_step {
    input:
      input_fastq = input_fastq,
      threads = threads,
      sequencing_tech = sequencing_tech,
      min_length = min_length,
      min_quality = min_quality,
      host_reference = host_reference,
      downsample = downsample
  }

  call PP.RunRosa as clean_rosa_step {
    input:
      fastq_file = preprocess_step.clean_fastq,
      sample_id = "clean"
  }

  call AS.assemble_and_select as assemble_step {
    input:
      clean_fastq = preprocess_step.clean_fastq,
      threads = threads,
      assembler = assembler,
      polish = polish,
      short_reads1 = short_reads1,
      short_reads2 = short_reads2,
      checkm2_db_path = checkm2_db_path
  }

  call BN.bin_and_checkm2 as bin_step {
    input:
      raw_contigs = assemble_step.tobe_binned_fasta,
      reads_fastq = preprocess_step.clean_fastq,
      threads = threads,
      assembler = assembler,
      sequencing_tech = sequencing_tech,
      binning_mode = binning_mode,
      checkm2_db_path = checkm2_db_path
  }

  # Optional classification: only run if skani_database is provided
  if (defined(skani_database)) {
    call CL.classify_bins as classify_step {
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
  call SM.summarize_results as summary_step {
    input:
      scMAGs = assemble_step.scMAGs,
      scMAGs_info = assemble_step.scMAGs_info,
      bins = bin_step.bins,
      bins_quality_report = bin_step.quality_report,
      classification_tsv = classify_step?.classify_result,
      fastq = preprocess_step.clean_fastq,
      threads = threads
  }

  # Make a report, taxonomic information  optional
  call SM.make_report as report_step {
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
