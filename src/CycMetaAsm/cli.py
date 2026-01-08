"""Command-line interface for CycMetaAsm."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Optional
from Bio import SeqIO

import pandas as pd

if __package__ is None or __package__ == "":  # pragma: no cover - execution as script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "CycMetaAsm"

from .pipelines.assembly import AssemblyConfig, AssemblyRunner
from .pipelines.binning import BinningConfig, run_binning
from .pipelines.classify import ClassificationConfig, Classifier
from .pipelines.evaluation import ContigAnalyzer, EvaluationConfig
from .pipelines.preprocess import run_preprocess
from .pipelines.summary import process_files

# from .pipelines.workflow import PipelineConfig, run_pipeline
from .utils import is_fastq_file, preset_setting, setup_logging

_LOGGER = logging.getLogger(__name__)


def parse_size(size_str: str) -> int:
    size_str = size_str.strip().upper()
    units = {
        "G": 10**9,
        "GB": 10**9,
        "M": 10**6,
        "MB": 10**6,
        "K": 10**3,
        "KB": 10**3,
    }
    for suffix, multiplier in units.items():
        if size_str.endswith(suffix):
            return int(float(size_str[: -len(suffix)]) * multiplier)
    return int(float(size_str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cycmetaasm", description="CycMetaAsm metagenomic toolkit"
    )
    parser.add_argument(
        "--log-level", default="INFO", help="Logging level (default: INFO)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preprocess = subparsers.add_parser(
        "preprocess", help="Downsample, filter, and remove host reads"
    )
    preprocess.add_argument("input", help="FASTQ input")
    preprocess.add_argument("output", help="Output directory")
    preprocess.add_argument("--threads", type=int, default=10)
    preprocess.add_argument(
        "--downsample", type=parse_size, help="Target bases, e.g. 10G"
    )
    preprocess.add_argument("--min-length", type=int, default=1000)
    preprocess.add_argument("--min-quality", type=int, default=7)
    preprocess.add_argument("--host-reference", help="Reference fasta for host removal")
    preprocess.add_argument(
        "--sequencing-tech",
        choices=["HiFi", "NanoPore", "CycloneSEQ"],
        default="CycloneSEQ",
        help="Sequencing technology preset",
    )

    assemble = subparsers.add_parser(
        "assemble", help="Run assembly for a processed FASTQ"
    )
    assemble.add_argument("input", help="FASTQ input")
    assemble.add_argument("output", help="Output directory")
    assemble.add_argument(
        "--assembler", choices=["metaflye", "metamdbg"], default="metaflye"
    )
    assemble.add_argument("--threads", type=int, default=10)
    assemble.add_argument("--preset", help="Assembler preset override")
    assemble.add_argument("--polish", action="store_true")
    assemble.add_argument(
        "--polish-path",
        help="Set the output path for polishing results manually. If not set, defaults to <output>/polish",
        default=None,
    )
    assemble.add_argument(
        "--short-reads1",
        help="Path to paired short reads file (forward)",
        required=False,
    )
    assemble.add_argument(
        "--short-reads2",
        help="Path to paired short reads file (reverse)",
        required=False,
    )
    assemble.add_argument(
        "--checkm2-db",
        help="CheckM2 database path. Enable completeness-aware strategy post-assembly if provided",
        required=False,
    )
    assemble.add_argument(
        "--subset-path",
        help="Set the output path for  completeness-aware strategy post-assembly. Defaults to <output>/subset_contigs.",
        default=None,
    )

    evaluation = subparsers.add_parser("evaluate", help="Run contig evaluation")
    evaluation.add_argument("assembly", help="Assembly FASTA")
    evaluation.add_argument("output", help="Output directory")
    evaluation.add_argument("--assembler", default="metaflye")
    evaluation.add_argument("--threads", type=int, default=10)
    evaluation.add_argument("--assembly-info")
    evaluation.add_argument("--checkm2", action="store_true")
    evaluation.add_argument(
        "--database", default="uniref100.KO.1.dmnd", help="CheckM2 database path"
    )
    evaluation.add_argument("--metaquast", action="store_true")
    evaluation.add_argument(
        "--reference", required=False, help="Reference genomes for metaQUAST"
    )

    binning = subparsers.add_parser("bin", help="Run SemiBin2 binning")
    binning.add_argument("assembly", help="Assembly FASTA")
    binning.add_argument("reads", help="Reads FASTQ/FASTA")
    binning.add_argument("output", help="Output directory")
    binning.add_argument("--assembler", default="metaflye")
    binning.add_argument("--threads", type=int, default=10)
    binning.add_argument(
        "--binning-model",
        choices=[
            "human_gut",
            "dog_gut",
            "ocean",
            "soil",
            "cat_gut",
            "human_oral",
            "mouse_gut",
            "pig_gut",
            "built_environment",
            "wastewater",
            "chicken_caecum",
            "global",
        ],
        default="global",
    )
    binning.add_argument(
        "--sequencing-tech",
        choices=["HiFi", "NanoPore", "CycloneSEQ"],
        default="CycloneSEQ",
    )
    binning.add_argument("--checkm2-db", help="CheckM2 database path", required=False)

    classify = subparsers.add_parser(
        "classify", help="Classify bins using skani or kMetaShot"
    )
    classify.add_argument("bins", help="Bins directory")
    classify.add_argument("output", help="Output directory")
    classify.add_argument("--database", help="The pre-generated ", required=True)
    classify.add_argument("--metadata", required=True)
    classify.add_argument("--assembler", default="metaflye")
    classify.add_argument("--threads", type=int, default=10)
    classify.add_argument("--tool", default="skani")
    classify.add_argument("--ass2ref", type=float, default=0.5)

    summarize = subparsers.add_parser(
        "summarize", help="Generate summary table and plots"
    )
    summarize.add_argument("bins_quality_report", help="CheckM2 quality report TSV")
    summarize.add_argument("output", help="Summary output directory")
    summarize.add_argument("--threads", type=int, default=10)
    summarize.add_argument(
        "--classification", help="Classification TSV", required=False
    )
    summarize.add_argument("--mag-path", help="Path to MAGs directory", required=False)
    summarize.add_argument(
        "--scmag-info", help="Path to scMAGs info TSV file", required=False
    )
    summarize.add_argument(
        "--fastq-file",
        help="Path to original FASTQ file for abundance profile",
        required=False,
    )

    # pipeline = subparsers.add_parser(
    #     "pipeline", help="Run the full end-to-end workflow"
    # )
    # pipeline.add_argument("input", help="FASTQ or FASTA input")
    # pipeline.add_argument("output", help="Output directory")
    # pipeline.add_argument("--threads", type=int, default=10)
    # pipeline.add_argument(
    #     "--sequencing-tech",
    #     choices=["HiFi", "NanoPore", "CycloneSEQ"],
    #     default="CycloneSEQ",
    # )
    # pipeline.add_argument("--assembler", nargs="+", default=["metaflye"])
    # pipeline.add_argument("--downsample", type=parse_size)
    # pipeline.add_argument("--min-length", type=int, default=1000)
    # pipeline.add_argument("--min-quality", type=int, default=7)
    # pipeline.add_argument("--host-reference")
    # pipeline.add_argument("--polish", action="store_true")
    # pipeline.add_argument("--short-reads1")
    # pipeline.add_argument("--short-reads2")
    # pipeline.add_argument("--database")
    # pipeline.add_argument("--reference")
    # pipeline.add_argument("--assembly-info")
    # pipeline.add_argument("--classify-tool", default="skani")

    return parser


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    setup_logging(getattr(logging, str(args.log_level).upper(), logging.INFO))

    if args.command == "preprocess":
        if not is_fastq_file(args.input):
            parser.error("preprocess requires a FASTQ input")
        presets = preset_setting(args.sequencing_tech)
        result = run_preprocess(
            args.input,
            args.output,
            args.threads,
            downsample_bases=args.downsample,
            min_length=args.min_length,
            min_quality=args.min_quality,
            host_reference=args.host_reference,
            minimap2_preset=presets["minimap2"],
        )
        _LOGGER.info("Preprocessing completed: %s", result.fastq_path)
        return

    if args.command == "assemble":
        if not is_fastq_file(args.input):
            parser.error("assemble expects a FASTQ input; use evaluate for FASTA")
        preset = args.preset or preset_setting("CycloneSEQ")[args.assembler]
        if polish_path := args.polish_path:
            polish_path = Path(args.polish_path)
        else:
            polish_path = Path(args.output) / "polish"
        config = AssemblyConfig(
            fastq_path=Path(args.input),
            output_dir=Path(args.output),
            assembler=args.assembler,
            threads=args.threads,
            preset=preset,
            polish=args.polish,
            polish_dir=polish_path,
            short_reads1=Path(args.short_reads1) if args.short_reads1 else None,
            short_reads2=Path(args.short_reads2) if args.short_reads2 else None,
        )
        result = AssemblyRunner(config).run()
        _LOGGER.info("Assembly completed: %s", str(result.fasta_path))
        # Completeness-aware strategy
        # Long contigs >500kb with >= 93% are move to the final MAG set, one contig per MAG
        # Only if CheckM2 database is provided
        if args.checkm2_db:
            if subset_path := args.subset_path:
                subset_dir = Path(subset_path)
            else:
                subset_dir = Path(args.output) / "subset_contigs"
            evaluation = ContigAnalyzer(
                EvaluationConfig(
                    assembly_fasta=result.fasta_path,
                    output_dir=str(subset_dir),
                    assembler=args.assembler,
                    threads=args.threads,
                    database_path=args.checkm2_db,
                )
            )
            contig_info = evaluation.get_contig_info()
            high_quality_contigs = [
                cid
                for cid, info in contig_info.items()
                if int(info.get("Length", 0)) >= 500_000
                and float(info.get("Completeness", 0)) >= 93.0
            ]
            if high_quality_contigs:
                _LOGGER.info(
                    "%s high-quality contigs identified for MAGs",
                    len(high_quality_contigs),
                )
                mag_dir = subset_dir / "scMAGs"
                mag_dir.mkdir(parents=True, exist_ok=True)
                tobe_binned_assembly = subset_dir / "to_be_binned.fasta"
                with (
                    open(result.fasta_path) as asm_handle,
                    open(tobe_binned_assembly, "w") as bin_handle,
                ):
                    for record in SeqIO.parse(asm_handle, "fasta"):
                        cid = record.description.split()[0]
                        if cid in high_quality_contigs:
                            mag_path = mag_dir / f"{cid}.fa"
                            SeqIO.write(record, mag_path, "fasta")
                        else:
                            SeqIO.write(record, bin_handle, "fasta")
                _LOGGER.info("Contigs for binning written to %s", tobe_binned_assembly)
                high_quality_contigs_info = {
                    cid: contig_info[cid] for cid in high_quality_contigs
                }
                high_quality_contigs_info_df = pd.DataFrame.from_dict(
                    high_quality_contigs_info, orient="index"
                )
                high_quality_contigs_info_df.index.name = "Contig"
                high_quality_contigs_info_df.to_csv(
                    mag_dir / "scMAGs_info.tsv", sep="\t"
                )
            else:
                _LOGGER.info("No high-quality contigs identified for MAGs")
                # All contigs copied to the to_be_binned.fasta
                tobe_binned_assembly = subset_dir / "to_be_binned.fasta"
                Path(tobe_binned_assembly).write_text(
                    Path(result.fasta_path).read_text()
                )
                _LOGGER.info("All contigs written to %s", tobe_binned_assembly)
        return

    if args.command == "evaluate":
        evaluation = ContigAnalyzer(
            EvaluationConfig(
                assembly_fasta=args.assembly,
                output_dir=args.output,
                assembler=args.assembler,
                threads=args.threads,
                assembly_info=args.assembly_info,
                database_path=args.database,
                reference=args.reference,
            )
        )
        info = evaluation.get_contig_info()
        output_dir = (
            Path(args.output)
            / "evaluation"
            / args.assembler
            / "assembly_contigs_info.tsv"
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame.from_dict(info, orient="index").to_csv(output_dir, sep="\t")
        if args.metaquastq:
            evaluation.run_metaquast()
        if args.checkm2:
            evaluation.run_checkm2()
        return

    if args.command == "bin":
        presets = preset_setting(args.sequencing_tech)
        config = BinningConfig(
            assembly_fasta=args.assembly,
            reads_path=args.reads,
            output_dir=args.output,
            assembler=args.assembler,
            threads=args.threads,
            minimap2_preset=presets["minimap2"],
            binning_mode=args.binning_model,
        )
        result = run_binning(config)
        _LOGGER.info("Binning completed: %s", result.bins_directory)
        # Run checkm2 on bins within bin command if database is provided
        if args.checkm2_db:
            evaluation = ContigAnalyzer(
                EvaluationConfig(
                    assembly_fasta=result.bins_directory,
                    output_dir=args.output,
                    assembler=f"{args.assembler}_bins",
                    threads=args.threads,
                    database_path=args.checkm2_db,
                )
            )
            quality_report = evaluation.run_checkm2()
            _LOGGER.info("CheckM2 quality report: %s", quality_report)
        return

    if args.command == "classify":
        classifier = Classifier(
            ClassificationConfig(
                bins_dir=args.bins,
                database=args.database,
                metadata=args.metadata,
                threads=args.threads,
                assembler=args.assembler,
                output_dir=args.output,
                tool=args.tool,
                ass2ref=args.ass2ref,
            )
        )
        classification = classifier.run()
        _LOGGER.info(
            "Classification outputs: %s, %s",
            classification.full,
            classification.deduplicated,
        )
        return

    if args.command == "summarize":
        result = process_files(
            args.bins_quality_report,
            args.output,
            args.classification,
            args.mag_path,
            args.scmag_info,
            args.fastq_file,
            args.threads,
        )
        _LOGGER.info("Summary written to %s", result)
        return

    # if args.command == "pipeline":
    #     config = PipelineConfig(
    #         input_path=args.input,
    #         output_dir=args.output,
    #         threads=args.threads,
    #         sequencing_technology=args.sequencing_tech,
    #         assemblers=args.assembler,
    #         downsample_bases=args.downsample,
    #         filter_min_length=args.min_length,
    #         filter_min_quality=args.min_quality,
    #         host_reference=args.host_reference,
    #         polish=args.polish,
    #         short_reads1=args.short_reads1,
    #         short_reads2=args.short_reads2,
    #         database=args.database,
    #         reference=args.reference,
    #         assembly_info=args.assembly_info,
    #         classify_tool=args.classify_tool,
    #     )
    #     run_pipeline(config)
    #     return

    parser.error(f"Unknown command: {args.command}")
