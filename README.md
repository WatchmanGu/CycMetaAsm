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

使用metaflye（目前只支持该组装软件）进行组装,组装结果输出在指定输出目录下，主要看`assembly.fasta`和`assembly_info.txt`（记录了contig长度、是否成环等信息）。组装完成，会在指定输出目录下生成`_isDone`文件作为标志。当再次运行组装命令时，如果发现该标志文件存在，则会跳过组装步骤，直接使用已有的组装结果。
启用`--polish`参数后，会进行组装后的短序列纠错，纠错结果会生成在组装结果输出目录的`polish`子目录通过`--polish-path`参数指定的纠错结果目录下，主要看`genome.nextpolish.fasta`。如果提供了短序列数据（`--short-reads1`和`--short-reads2`），则会使用这些短序列进行混合组装后的纠错，否则只使用长序列进行自我纠错。使用短序列数据时，会先调用`fastp`进行短序列的质量控制和过滤，然后再进行纠错。短序列质控结果会生成在纠错结果目录的`short_reads_qc`子目录下，主要看`filter_1.fq.gz`和`filter_2.fq.gz`，并且同样使用`_isDone`文件作为质控完成的标志。纠错完成，会在纠错结果目录下生成`_isDone`文件作为标志。当再次运行组装命令时，如果发现该标志文件存在，则会跳过纠错步骤，直接使用已有的纠错结果。
启用`--checkm2-db`参数后，会启用completeness-aware策略，在组装完成后对组装结果或纠错结果（如果启用了纠错）进行CheckM2质量评估，然后根据评估结果筛选completenes≥93%的长序列（≥500kb）作为高质量单contig MAGs（scMAGs）单独存放在`scMAGs`子目录下（每个contig一个fasta文件，并伴有`scMAGs_info.tsv`记录contig ID以及质量信息）跳过binning步骤，其余contig会被输出到`to_be_binned.fasta`文件中供后续binning使用。可通过`--subset-path`参数指定启用completeness-aware策略的结果输出路径，默认是直接在组装结果输出目录下生成`subset_contigs`子目录。
注意，CheckM2质量评估输出目录隐式设定为completeness-aware策略结果输出路径的`checkm2`子目录。

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
使用SemiBin2对组装结果进行binning。输入的组装结果可以是完整的组装结果（`assembly.fasta`），也可以是completeness-aware策略筛选后的待binning序列（`to_be_binned.fasta`）。可通过`--binning-model`参数指定SemiBin2的binning模型，默认`global`（默认）和`single`两种模式，分别对应多样本联合binning和单样本独立binning。完成后会在Binnning结果目录下生成`output_bins`子目录，里面包含了所有的bins（每个bin一个fasta文件），并使用`_isDone`文件作为binning完成的标志。当再次运行binning命令时，如果发现该标志文件存在，则会跳过binning步骤，直接使用已有的binning结果。
启用`--checkm2-db`参数后，会在binning完成后对bins进行CheckM2质量评估，评估结果会输出在Binnning结果目目录下的`checkm2`子目录下，主要看`quality_report.tsv`文件。同样使用`_isDone`文件作为质量评估完成的标志。当再次运行binning命令时，如果发现该标志文件存在，则会跳过质量评估步骤，直接使用已有的评估结果。

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
