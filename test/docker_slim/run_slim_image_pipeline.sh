#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

IMAGE=${IMAGE:-cycmetaasm:v1.1.0}
DOCKER_USER=${DOCKER_USER:-$(id -u):$(id -g)}
THREADS=${THREADS:-4}
POLISH=${POLISH:-0}
MIN_LENGTH=${MIN_LENGTH:-1000}
MIN_QUALITY=${MIN_QUALITY:-10}
OUTPUT_ROOT=${OUTPUT_ROOT:-${ROOT}/test/docker_slim/output}
INPUT_FASTQ=${INPUT_FASTQ:-${ROOT}/wdl/test/sample.fastq.gz}
CHECKM2_DB=${CHECKM2_DB:-/data/gukaijie/project/database/checkm2/CheckM2_database}
HOST_REFERENCE=${HOST_REFERENCE:-/data/gukaijie/project/database/NCBI_genome/human/datasets_GCF_000001405.40/data/GCF_000001405.40/GCF_000001405.40_GRCh38.p14_genomic.fna}
SKANI_DATABASE=${SKANI_DATABASE:-/data/gukaijie/project/02.metagenomic/workflow/CycMetaAsm/database4classifier}
SKANI_METADATA=${SKANI_METADATA:-${SKANI_DATABASE}/metadata.tsv}

if [[ -d "${CHECKM2_DB}" ]]; then
  if [[ -f "${CHECKM2_DB}/uniref100.KO.1.dmnd" ]]; then
    CHECKM2_DB="${CHECKM2_DB}/uniref100.KO.1.dmnd"
  else
    shopt -s nullglob
    checkm2_candidates=("${CHECKM2_DB}"/*.dmnd)
    shopt -u nullglob
    if [[ "${#checkm2_candidates[@]}" -eq 1 ]]; then
      CHECKM2_DB="${checkm2_candidates[0]}"
    else
      printf 'CHECKM2_DB directory must contain exactly one .dmnd database file: %s\n' "${CHECKM2_DB}" >&2
      exit 2
    fi
  fi
fi

for path in "${INPUT_FASTQ}" "${CHECKM2_DB}" "${HOST_REFERENCE}" "${SKANI_DATABASE}" "${SKANI_METADATA}"; do
  if [[ ! -e "${path}" ]]; then
    printf 'Required path not found: %s\n' "${path}" >&2
    exit 2
  fi
done

if [[ "${INPUT_FASTQ}" == "${ROOT}"/* ]]; then
  input_relpath=${INPUT_FASTQ#"${ROOT}"/}
  INPUT_FASTQ_DOCKER="/repo/${input_relpath}"
elif [[ "${INPUT_FASTQ}" == /data/* ]]; then
  INPUT_FASTQ_DOCKER="${INPUT_FASTQ}"
else
  printf 'INPUT_FASTQ must be under the repository or /data so Docker can mount it: %s\n' "${INPUT_FASTQ}" >&2
  exit 2
fi

docker image inspect "${IMAGE}" >/dev/null

POLISH_FLAG=()
case "${POLISH}" in
  1|true|TRUE) POLISH_FLAG=(--polish) ;;
  0|false|FALSE) ;;
  *)
    printf 'POLISH must be 1, true, 0, or false: %s\n' "${POLISH}" >&2
    exit 2
    ;;
esac

mkdir -p "$(dirname "${OUTPUT_ROOT}")"
if [[ -d "${OUTPUT_ROOT}" ]]; then
  docker run --rm \
    -v "${OUTPUT_ROOT}:/work" \
    "${IMAGE}" \
    sh -lc 'rm -rf /work/* /work/.[!.]* /work/..?*'
fi
mkdir -p "${OUTPUT_ROOT}"

docker run --rm \
  --user "${DOCKER_USER}" \
  -v "${ROOT}:/repo:ro" \
  -v "/data:/data:ro" \
  -v "${OUTPUT_ROOT}:/work" \
  -w /work \
  -e HOME=/tmp \
  -e THREADS="${THREADS}" \
  -e MIN_LENGTH="${MIN_LENGTH}" \
  -e MIN_QUALITY="${MIN_QUALITY}" \
  -e INPUT_FASTQ_DOCKER="${INPUT_FASTQ_DOCKER}" \
  -e CHECKM2_DB="${CHECKM2_DB}" \
  -e HOST_REFERENCE="${HOST_REFERENCE}" \
  -e SKANI_DATABASE="${SKANI_DATABASE}" \
  -e SKANI_METADATA="${SKANI_METADATA}" \
  -e POLISH_FLAG="${POLISH_FLAG[*]}" \
  "${IMAGE}" \
  bash -c '
    set -euo pipefail
    cycmetaasm pipeline "${INPUT_FASTQ_DOCKER}" output \
      --threads "${THREADS}" \
      --sequencing-tech CycloneSEQ \
      --assembler myloasm \
      --binner lorbin \
      --min-length "${MIN_LENGTH}" \
      --min-quality "${MIN_QUALITY}" \
      --host-reference "${HOST_REFERENCE}" \
      --checkm2-db "${CHECKM2_DB}" \
      --skani-database "${SKANI_DATABASE}" \
      --skani-metadata "${SKANI_METADATA}" \
      --classify-tool skani \
      --classify-ass2ref 0.5 \
      ${POLISH_FLAG} \
      --keep-intermediate-files
  '

docker run --rm \
  --user "${DOCKER_USER}" \
  -v "${ROOT}:/repo:ro" \
  -v "/data:/data:ro" \
  -v "${OUTPUT_ROOT}:/work" \
  -w /work \
  -e HOME=/tmp \
  -e THREADS="${THREADS}" \
  -e INPUT_FASTQ_DOCKER="${INPUT_FASTQ_DOCKER}" \
  "${IMAGE}" \
  bash -c '
    set -euo pipefail

    rm -rf report
    mkdir -p \
      report/raw_rosa \
      report/clean_rosa \
      report/final/results/raw_rosa_results \
      report/final/results/clean_rosa_results

    cd /work/report/raw_rosa
    rosa \
      -i "${INPUT_FASTQ_DOCKER}" \
      --sample-name raw \
      --seed 9999 \
      --sample-size 100000 \
      -o result \
      -t 4
    test -f result/report.html
    mv result/report.html result/raw_QC_report.html
    zip -qr raw_QC_results.zip result/

    cd /work/report/clean_rosa
    rosa \
      -i /work/output/preprocess/remove_host/host_removed.fastq.gz \
      --sample-name clean \
      --seed 9999 \
      --sample-size 100000 \
      -o result \
      -t 4
    test -f result/report.html
    mv result/report.html result/clean_QC_report.html
    zip -qr clean_QC_results.zip result/

    cp \
      /work/report/raw_rosa/result/fastx_analyses/figures/read_length_distribution.png \
      /work/report/raw_rosa/result/fastx_analyses/figures/read_quality_distribution.png \
      /work/report/raw_rosa/result/fastx_analyses/figures/cumulative_read_length.png \
      /work/report/raw_rosa/result/fastx_analyses/figures/read_length_vs_quality.png \
      /work/report/raw_rosa/result/fastx_analyses/results/reference-free_QC_results_summary.tsv \
      /work/report/final/results/raw_rosa_results/
    cp \
      /work/report/clean_rosa/result/fastx_analyses/figures/read_length_distribution.png \
      /work/report/clean_rosa/result/fastx_analyses/figures/read_quality_distribution.png \
      /work/report/clean_rosa/result/fastx_analyses/figures/cumulative_read_length.png \
      /work/report/clean_rosa/result/fastx_analyses/figures/read_length_vs_quality.png \
      /work/report/clean_rosa/result/fastx_analyses/results/reference-free_QC_results_summary.tsv \
      /work/report/final/results/clean_rosa_results/

    cp -r \
      /work/report/raw_rosa/raw_QC_results.zip \
      /work/report/clean_rosa/clean_QC_results.zip \
      /work/output/summary/summary.tsv \
      /work/output/summary/top_ranked_mag_summary.tsv \
      /work/output/summary/passed_quality_mags \
      /work/output/summary/low_quality_mags \
      /work/output/summary/quality_stats.tsv \
      /work/output/summary/rank_completeness_contamination.png \
      /work/output/summary/contig_n50_violin.png \
      /work/report/final/results/
    if [[ -f /work/output/summary/taxonomic_abundance.html ]]; then
      cp /work/output/summary/taxonomic_abundance.html /work/report/final/results/
    fi

    cycloneseq-report /repo/wdl/config/report_config.yaml \
      -o /work/report/final/results/sample_CycMetaAsm_Report.html \
      -w /work/report/final/results/

    rm -rf \
      /work/report/final/results/clean_rosa_results \
      /work/report/final/results/raw_rosa_results
    mv /work/report/final/results /work/report/final/sample_CycMetaAsm_Results
    cd /work/report/final
    zip -qr sample_CycMetaAsm_Results.zip sample_CycMetaAsm_Results/
    paste -d "\t" \
      <(printf "Sample_id\nsample\n") \
      sample_CycMetaAsm_Results/quality_stats.tsv > summary.txt
  '

required_outputs=(
  "output/preprocess/remove_host/host_removed.fastq.gz"
  "output/assembly/assembly.fasta"
  "output/subset_contigs/to_be_binned.fasta"
  "output/binning/output_bins"
  "output/binning/checkm2/quality_report.tsv"
  "output/classify/classify_result_deduplicated.tsv"
  "output/summary/summary.tsv"
  "output/summary/quality_stats.tsv"
  "report/raw_rosa/raw_QC_results.zip"
  "report/clean_rosa/clean_QC_results.zip"
  "report/final/sample_CycMetaAsm_Results/sample_CycMetaAsm_Report.html"
  "report/final/sample_CycMetaAsm_Results.zip"
  "report/final/summary.txt"
)

for relpath in "${required_outputs[@]}"; do
  if [[ ! -e "${OUTPUT_ROOT}/${relpath}" ]]; then
    printf 'Expected output missing: %s\n' "${OUTPUT_ROOT}/${relpath}" >&2
    exit 3
  fi
done

if [[ "${POLISH}" == "1" || "${POLISH}" == "true" || "${POLISH}" == "TRUE" ]]; then
  polish_outputs=(
    "output/assembly/polish/genome.nextpolish.fasta"
    "output/assembly/polish/_isDone"
    "output/assembly/polish/run.cfg"
    "output/assembly/polish/lgs.fofn"
  )
  for relpath in "${polish_outputs[@]}"; do
    if [[ ! -e "${OUTPUT_ROOT}/${relpath}" ]]; then
      printf 'Expected polish output missing: %s\n' "${OUTPUT_ROOT}/${relpath}" >&2
      exit 3
    fi
  done
fi

bin_count=$(find "${OUTPUT_ROOT}/output/binning/output_bins" -maxdepth 1 -name "*.fa" | wc -l)
if [[ "${bin_count}" -eq 0 ]]; then
  printf 'Expected at least one LorBin output bin\n' >&2
  exit 4
fi

printf 'Slim CycMetaAsm Docker pipeline test completed: %s/output\n' "${OUTPUT_ROOT}"
printf 'LorBin bins: %s\n' "${bin_count}"
printf 'Final report: %s/report/final/sample_CycMetaAsm_Results/sample_CycMetaAsm_Report.html\n' "${OUTPUT_ROOT}"
