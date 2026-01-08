version 1.0
task preprocess {
  input {
    File input_fastq
    Int threads = 10
    String sequencing_tech = "CycloneSEQ"
    Int min_length = 1000
    Int min_quality = 10
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

        # Case 1: Value < 0.1 → Only warn, do not apply downsampling
        awk_res=$(awk -v v="$ds" 'BEGIN {if (v < 0.1) print "lt"; else print "ge"}')
        if [[ "$awk_res" == "lt" ]]; then
            echo "[WARNING] The sampled data volume is too small; assembly may fail!" >&2
            # Do NOT enable downsampling
        else
            # Case 2: Value == 0 → Disable downsampling
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
