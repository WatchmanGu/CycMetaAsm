"""High-level orchestration mirroring the legacy main.py pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

from ..utils import is_fasta_file, is_fastq_file, preset_setting, setup_logging
from .assembly import AssemblyConfig, AssemblyRunner
from .binning import BinningConfig, run_binning
from .classify import ClassificationConfig, Classifier
from .evaluation import ContigAnalyzer, EvaluationConfig
from .preprocess import PreprocessResult, run_preprocess
from .summary import process_files

_LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    input_path: str
    output_dir: str
    threads: int = 10
    sequencing_technology: str = "NanoPore"
    assemblers: List[str] = field(default_factory=lambda: ["metaflye"])
    downsample_bases: Optional[int] = None
    filter_min_length: int = 1000
    filter_min_quality: int = 7
    host_reference: Optional[str] = None
    polish: bool = False
    short_reads1: Optional[str] = None
    short_reads2: Optional[str] = None
    database: Optional[str] = None
    reference: Optional[str] = None
    assembly_info: Optional[str] = None
    classify_tool: str = "skani"


def run_pipeline(config: PipelineConfig) -> None:
    setup_logging()
    _LOGGER.info("Starting CycMetaAsm pipeline")

    output_root = Path(config.output_dir) / config.sequencing_technology
    output_root.mkdir(parents=True, exist_ok=True)
    presets = preset_setting(config.sequencing_technology)

    processed_fastq = config.input_path
    preprocess_result: Optional[PreprocessResult] = None
    if is_fastq_file(config.input_path):
        preprocess_result = run_preprocess(
            config.input_path,
            str(output_root),
            config.threads,
            downsample_bases=config.downsample_bases,
            min_length=config.filter_min_length,
            min_quality=config.filter_min_quality,
            host_reference=config.host_reference,
            minimap2_preset=presets["minimap2"],
        )
        processed_fastq = preprocess_result.fastq_path
        _LOGGER.info("Preprocessing output: %s", processed_fastq)
    elif is_fasta_file(config.input_path):
        _LOGGER.info("Input detected as FASTA; skipping preprocessing")
    else:
        raise ValueError("Input file must be FASTQ or FASTA")

    assembler_results = []
    for assembler_name in config.assemblers:
        assembler_key = assembler_name.lower()
        preset = presets.get(assembler_key)
        if preset is None:
            raise ValueError(f"No preset for assembler '{assembler_name}'")
        asm_config = AssemblyConfig(
            fastq_path=processed_fastq,
            output_dir=str(output_root),
            assembler=assembler_key,
            threads=config.threads,
            preset=preset,
            polish=config.polish,
            short_reads1=config.short_reads1,
            short_reads2=config.short_reads2,
        )
        runner = AssemblyRunner(asm_config)
        result = runner.run()
        assembler_results.append(result)

    for result in assembler_results:
        assembler_name = Path(result.fasta_path).parent.name
        evaluation = ContigAnalyzer(
            EvaluationConfig(
                assembly_fasta=result.fasta_path,
                output_dir=str(output_root),
                assembler=assembler_name,
                threads=config.threads,
                assembly_info=result.assembly_info or config.assembly_info,
                database_path=config.database,
                reference=config.reference,
            )
        )
        contig_info = evaluation.get_contig_info()
        report_dir = Path(output_root) / "evaluation" / assembler_name / "singleContigs"
        report_dir.mkdir(parents=True, exist_ok=True)
        contig_df = pd.DataFrame.from_dict(contig_info, orient="index")
        contig_df.index.name = "Contig"
        contig_df.to_csv(report_dir / "assembly_contigs_info.tsv", sep="\t")
        if config.reference:
            evaluation.run_metaquast()

        binning = run_binning(
            BinningConfig(
                assembly_fasta=result.fasta_path,
                reads_path=processed_fastq,
                output_dir=str(output_root),
                assembler=assembler_name,
                threads=config.threads,
                minimap2_preset=presets["minimap2"],
            )
        )
        bin_evaluation = ContigAnalyzer(
            EvaluationConfig(
                assembly_fasta=binning.bins_directory,
                output_dir=str(output_root),
                assembler=f"{assembler_name}_bins",
                threads=config.threads,
                database_path=config.database,
                reference=config.reference,
            )
        )
        quality_report = bin_evaluation.run_checkm2() if config.database else ""
        if config.reference:
            bin_evaluation.run_metaquast()
        if not config.database:
            raise ValueError("Database path is required for classification")
        classifier = Classifier(
            ClassificationConfig(
                bins_dir=binning.bins_directory,
                database_root=config.database,
                threads=config.threads,
                assembler=assembler_name,
                tool=config.classify_tool,
            )
        )
        classification = classifier.run(str(output_root))
        process_files(
            quality_report,
            classification.deduplicated,
            str(Path(output_root) / "Summary" / assembler_name),
        )
