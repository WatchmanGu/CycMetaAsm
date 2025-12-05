version 1.0

task preprocess {
  input {
    File input_fastq
    Int threads = 10
    String sequencing_tech = "CycloneSEQ"
    Int min_length = 1000
    Int min_quality = 10
    File? host_reference
    String? downsample
  }

  command <<<
    set -euo pipefail

    mkdir -p work

    cycmetaasm preprocess ~{input_fastq} work \
      --threads ~{threads} \
      --sequencing-tech ~{sequencing_tech} \
      --min-length ~{min_length} \
      --min-quality ~{min_quality} \
      ~{if defined(host_reference) then "--host-reference " + host_reference else ""} \
      ~{if defined(downsample) then "--downsample " + downsample else ""}

    cp ~{if defined(host_reference) then "work/remove_host/host_removed.fastq.gz" else "work/qc/filtered.fastq.gz"} clean.fastq.gz
  >>>

  output {
    File clean_fastq = "clean.fastq.gz"
  }

  runtime {
    docker: "cycmetaasm:v1.0.0"
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
        docker: "rosa:0.2.14.0"
        cpu: 10
        memory: 32 + "GB"
    }
}
