# CycMetaAsm

## Long-read Metagenomic Assembly and MAG Analysis Toolkit (CycloneSEQ)

CycMetaAsm is a comprehensive bioinformatics pipeline designed for processing long-read metagenomic sequencing data, specifically optimized for the CycloneSEQ platform. It automates the entire workflow from raw data processing to the generation of high-quality Metagenome-Assembled Genomes (MAGs) and taxonomic profiles.

## Features

Based on the `CycMetaAsmWorkflow`, the pipeline includes the following key stages:

1. **Sequencing Data QC**: Evaluates read length distribution, GC content, and base quality using Rosa.
2. **Read Preprocessing**: Filters low-quality reads based on length and quality thresholds. Supports optional downsampling and host genome removal (e.g., human host).
3. **Metagenome Assembly & Polishing**: Constructs assembly graphs using **metaFlye** or **metaMDBG**. Supports optional polishing with short reads (hybrid assembly approach).
4. **Binning & Quality Assessment**: Recovers MAGs using **SemiBin2** and assesses genome completeness and contamination with **CheckM2**.
    * *Completeness-aware strategy*: High-quality long contigs (>500kb, >93% completeness) are identified as single-contig MAGs (scMAGs) before binning.
5. **Taxonomic Annotation & Abundance**: Performs taxonomic classification of bins using **skani** or **kMetaShot** and estimates abundance.

## Installation

### Development Install

To install the package in editable mode for development:

```bash
pip install --upgrade pip
pip install -e .
```

### Compilation (Nuitka)

The project is designed to be compiled into a standalone executable using Nuitka:

```bash
pip install --upgrade pip nuitka
python -m nuitka \
  --onefile \
  --standalone \
  --include-package=CycMetaAsm \
  --include-package=plotly \
  --include-package-data=plotly \
  --output-dir=build \
    src/CycMetaAsm
```

## Usage

The toolkit provides a subcommand-oriented CLI `cycmetaasm`.

### Quick Start: Full Pipeline

Run the complete end-to-end workflow:

```bash
cycmetaasm pipeline input.fastq.gz output_dir \
  --threads 40 \
  --sequencing-tech CycloneSEQ \
  --assembler metaflye \
  --host-reference database/GRCh38.p14.fa \
  --database database/skani_db \
  --classify-tool skani
```

### Subcommands

You can also run individual steps of the pipeline:

#### 1. Preprocess

Downsample, filter, and remove host reads.

```bash
cycmetaasm preprocess input.fastq.gz output_dir \
  --threads 10 \
  --downsample 10G \
  --min-length 1000 \
  --min-quality 10 \
  --host-reference database/GRCh38.p14.fa
```

#### 2. Assemble

Run assembly (metaFlye/metaMDBG) and optional polishing.

```bash
cycmetaasm assemble output_dir/clean.fastq.gz output_dir \
  --assembler metaflye \
  --threads 40 \
  --polish \
  --short-reads1 lib.1.fq.gz --short-reads2 lib.2.fq.gz \
  --checkm2-db database/CheckM2/uniref100.KO.1.dmnd
```

#### 3. Bin

Run SemiBin2 binning.

```bash
cycmetaasm bin assembly.fasta clean_reads.fastq output_dir \
  --binning-model global \
  --sequencing-tech CycloneSEQ \
  --checkm2-db database/CheckM2/uniref100.KO.1.dmnd
```

#### 4. Classify

Classify bins using skani.

```bash
cycmetaasm classify bins_dir output_dir \
  --tool skani \
  --database database/skani_db \
  --metadata metadata.tsv
```

#### 5. Summarize

Generate summary reports and plots.

```bash
cycmetaasm summarize checkm2_quality_report.tsv output_dir \
  --classification classification_result.tsv \
  --mag-path mags_dir \
  --fastq-file original.fastq.gz
```

## WDL Workflow

A WDL (Workflow Description Language) version of the pipeline is available in `wdl/workflow.wdl`. It orchestrates the same tasks defined in the Python CLI.

**Key Inputs:**

* `input_fastq`: Raw sequencing data.
* `host_reference`: Host genome for decontamination.
* `checkm2_db_path`: Database for CheckM2.
* `skani_database`: Database for taxonomic classification.
* `polish`: Boolean to enable polishing.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
