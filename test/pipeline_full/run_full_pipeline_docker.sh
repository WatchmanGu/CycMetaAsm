#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

IMAGE=${IMAGE:-cycmetaasm:v1.1.0}
THREADS=${THREADS:-4}
OUTPUT_ROOT=${OUTPUT_ROOT:-/tmp/opencode/cycmetaasm_full_pipeline_with_dbs}
INPUT_FASTQ=${INPUT_FASTQ:-${ROOT}/wdl/test/sample.fastq.gz}
CHECKM2_DB=${CHECKM2_DB:-/data/gukaijie/project/database/checkm2/CheckM2_database/uniref100.KO.1.dmnd}
HOST_REFERENCE=${HOST_REFERENCE:-/data/gukaijie/project/database/NCBI_genome/human/datasets_GCF_000001405.40/data/GCF_000001405.40/GCF_000001405.40_GRCh38.p14_genomic.fna}
SKANI_DATABASE=${SKANI_DATABASE:-/data/zhouan/Metagenome/metagenome_assembly/database/gtdb/r226/gtdb_r226_ani}
SKANI_METADATA=${SKANI_METADATA:-${SKANI_DATABASE}/metadata.tsv}

for path in "${INPUT_FASTQ}" "${CHECKM2_DB}" "${HOST_REFERENCE}" "${SKANI_DATABASE}" "${SKANI_METADATA}"; do
  if [[ ! -e "${path}" ]]; then
    echo "Required path not found: ${path}" >&2
    exit 2
  fi
done

if [[ "${INPUT_FASTQ}" == "${ROOT}"/* ]]; then
  input_relpath=${INPUT_FASTQ#"${ROOT}"/}
  INPUT_FASTQ_DOCKER="/repo/${input_relpath}"
elif [[ "${INPUT_FASTQ}" == /data/* ]]; then
  INPUT_FASTQ_DOCKER="${INPUT_FASTQ}"
else
  echo "INPUT_FASTQ must be under the repository or /data so Docker can mount it: ${INPUT_FASTQ}" >&2
  exit 2
fi

docker image inspect "${IMAGE}" >/dev/null

mkdir -p "$(dirname "${OUTPUT_ROOT}")"
rm -rf "${OUTPUT_ROOT}"
mkdir -p "${OUTPUT_ROOT}"

docker run --rm \
  -v "${ROOT}:/repo:ro" \
  -v "/data:/data:ro" \
  -v "${OUTPUT_ROOT}:/work" \
  -w /work \
  -e THREADS="${THREADS}" \
  -e INPUT_FASTQ_DOCKER="${INPUT_FASTQ_DOCKER}" \
  -e CHECKM2_DB="${CHECKM2_DB}" \
  -e HOST_REFERENCE="${HOST_REFERENCE}" \
  -e SKANI_DATABASE="${SKANI_DATABASE}" \
  -e SKANI_METADATA="${SKANI_METADATA}" \
  "${IMAGE}" \
  bash -c '
    set -euo pipefail
    cycmetaasm pipeline "${INPUT_FASTQ_DOCKER}" output \
      --threads "${THREADS}" \
      --sequencing-tech CycloneSEQ \
      --assembler myloasm \
      --binner lorbin \
      --host-reference "${HOST_REFERENCE}" \
      --checkm2-db "${CHECKM2_DB}" \
      --skani-database "${SKANI_DATABASE}" \
      --skani-metadata "${SKANI_METADATA}" \
      --classify-tool skani \
      --classify-ass2ref 0.5 \
      --keep-intermediate-files
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
)

for relpath in "${required_outputs[@]}"; do
  if [[ ! -e "${OUTPUT_ROOT}/${relpath}" ]]; then
    echo "Expected output missing: ${OUTPUT_ROOT}/${relpath}" >&2
    exit 3
  fi
done

bin_count=$(find "${OUTPUT_ROOT}/output/binning/output_bins" -maxdepth 1 -name "*.fa" | wc -l)
if [[ "${bin_count}" -eq 0 ]]; then
  echo "Expected at least one LorBin output bin" >&2
  exit 4
fi

echo "Full CycMetaAsm Docker pipeline test completed: ${OUTPUT_ROOT}/output"
echo "LorBin bins: ${bin_count}"
