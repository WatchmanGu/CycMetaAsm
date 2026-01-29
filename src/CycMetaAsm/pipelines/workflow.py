"""Full pipeline workflow orchestration."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .assembly import AssemblyConfig, AssemblyRunner
from .binning import BinningConfig, run_binning
from .classify import ClassificationConfig, Classifier
from .evaluation import ContigAnalyzer, EvaluationConfig
from .preprocess import run_preprocess
from .summary import process_files
from ..utils import preset_setting

_LOGGER = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the full CycMetaAsm pipeline."""
    
    input_path: str
    output_dir: str
    threads: int = 10
    sequencing_technology: str = "CycloneSEQ"
    assembler: str = "metaflye"
    
    # Preprocessing parameters
    downsample_bases: Optional[int] = None
    filter_min_length: int = 1000
    filter_min_quality: int = 7
    host_reference: Optional[str] = None
    
    # Assembly parameters
    polish: bool = False
    short_reads1: Optional[str] = None
    short_reads2: Optional[str] = None
    
    # CheckM2 database for quality assessment (required)
    checkm2_db: str
    
    # Binning parameters
    binning_mode: str = "global"
    
    # Classification parameters
    skani_database: Optional[str] = None
    skani_metadata: Optional[str] = None
    classify_tool: str = "skani"
    classify_ass2ref: float = 0.5
    
    # Cleanup parameter
    clean_intermediate_files: bool = True


def run_pipeline(config: PipelineConfig) -> None:
    """Run the complete CycMetaAsm pipeline.
    
    Args:
        config: Pipeline configuration
    """
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    presets = preset_setting(config.sequencing_technology)
    
    # Track intermediate files to clean up
    intermediate_files = []
    
    # ========== STEP 1: Preprocessing ==========
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 1: Preprocessing")
    _LOGGER.info("=" * 60)
    
    preprocess_dir = output_dir / "preprocess"
    preprocess_result = run_preprocess(
        config.input_path,
        str(preprocess_dir),
        config.threads,
        downsample_bases=config.downsample_bases,
        min_length=config.filter_min_length,
        min_quality=config.filter_min_quality,
        host_reference=config.host_reference,
        minimap2_preset=presets["minimap2"],
    )
    clean_fastq = preprocess_result.fastq_path
    _LOGGER.info("Preprocessing completed: %s", clean_fastq)
    
    # Track intermediate FASTQ files
    if config.downsample_bases:
        intermediate_files.append(preprocess_dir / "downsampled.fastq.gz")
    intermediate_files.append(preprocess_dir / "qc" / "filtered.fastq.gz")
    
    # ========== STEP 2: Assembly ==========
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 2: Assembly")
    _LOGGER.info("=" * 60)
    
    assembly_dir = output_dir / "assembly"
    preset = presets.get(config.assembler, presets["metaflye"])
    polish_dir = assembly_dir / "polish" if config.polish else None
    
    assembly_config = AssemblyConfig(
        fastq_path=Path(clean_fastq),
        output_dir=assembly_dir,
        assembler=config.assembler,
        threads=config.threads,
        preset=preset,
        polish=config.polish,
        polish_dir=polish_dir,
        short_reads1=Path(config.short_reads1) if config.short_reads1 else None,
        short_reads2=Path(config.short_reads2) if config.short_reads2 else None,
    )
    assembly_result = AssemblyRunner(assembly_config).run()
    _LOGGER.info("Assembly completed: %s", assembly_result.fasta_path)
    
    # ========== STEP 3: Contig Quality Assessment ==========
    scmags_dir = None
    scmags_info = None
    to_be_binned = assembly_result.fasta_path
    
    if config.checkm2_db:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 3: Contig Quality Assessment and Selection")
        _LOGGER.info("=" * 60)
        
        subset_dir = output_dir / "subset_contigs"
        evaluation = ContigAnalyzer(
            EvaluationConfig(
                assembly_fasta=assembly_result.fasta_path,
                output_dir=str(subset_dir),
                assembler=config.assembler,
                threads=config.threads,
                database_path=config.checkm2_db,
            )
        )
        contig_info = evaluation.get_contig_info()
        
        # Extract high-quality contigs (>=500kb and >=93% completeness)
        high_quality_contigs = [
            cid
            for cid, info in contig_info.items()
            if int(info.get("Length", 0)) >= 500_000
            and float(info.get("Completeness", 0)) >= 93.0
        ]
        
        if high_quality_contigs:
            import pandas as pd
            from Bio import SeqIO
            
            _LOGGER.info(
                "%d high-quality contigs identified for scMAGs",
                len(high_quality_contigs),
            )
            scmags_dir = subset_dir / "scMAGs"
            scmags_dir.mkdir(parents=True, exist_ok=True)
            to_be_binned = subset_dir / "to_be_binned.fasta"
            
            with (
                open(assembly_result.fasta_path) as asm_handle,
                open(to_be_binned, "w") as bin_handle,
            ):
                for record in SeqIO.parse(asm_handle, "fasta"):
                    cid = record.description.split()[0]
                    if cid in high_quality_contigs:
                        mag_path = scmags_dir / f"{cid}.fa"
                        SeqIO.write(record, mag_path, "fasta")
                    else:
                        SeqIO.write(record, bin_handle, "fasta")
            
            # Save scMAGs info
            scmags_info = scmags_dir / "scMAGs_info.tsv"
            high_quality_contigs_info = {
                cid: contig_info[cid] for cid in high_quality_contigs
            }
            high_quality_contigs_info_df = pd.DataFrame.from_dict(
                high_quality_contigs_info, orient="index"
            )
            high_quality_contigs_info_df.index.name = "Contig"
            high_quality_contigs_info_df.to_csv(scmags_info, sep="\t")
            _LOGGER.info("scMAGs written to %s", scmags_dir)
        else:
            _LOGGER.info("No high-quality contigs identified for scMAGs")
            # All contigs go to binning
            to_be_binned = subset_dir / "to_be_binned.fasta"
            shutil.copy2(assembly_result.fasta_path, to_be_binned)
    
    # ========== STEP 4: Binning ==========
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 4: Binning")
    _LOGGER.info("=" * 60)
    
    binning_dir = output_dir / "binning"
    binning_config = BinningConfig(
        assembly_fasta=str(to_be_binned),
        reads_path=clean_fastq,
        output_dir=str(binning_dir),
        assembler=config.assembler,
        threads=config.threads,
        minimap2_preset=presets["minimap2"],
        binning_mode=config.binning_mode,
    )
    binning_result = run_binning(binning_config)
    _LOGGER.info("Binning completed: %s", binning_result.bins_directory)
    
    # Track alignment files for cleanup
    intermediate_files.append(binning_dir / "aligned.bam")
    intermediate_files.append(binning_dir / "aligned.bam.bai")
    
    # Run CheckM2 on bins
    _LOGGER.info("Running CheckM2 on bins...")
    evaluation = ContigAnalyzer(
        EvaluationConfig(
            assembly_fasta=binning_result.bins_directory,
            output_dir=str(binning_dir),
            assembler=f"{config.assembler}_bins",
            threads=config.threads,
            database_path=config.checkm2_db,
        )
    )
    quality_report = evaluation.run_checkm2()
    _LOGGER.info("CheckM2 quality report: %s", quality_report)
    
    # ========== STEP 5: Classification ==========
    classification_result = None
    if config.skani_database and config.skani_metadata:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 5: Species Classification")
        _LOGGER.info("=" * 60)
        
        # Combine bins and scMAGs for classification
        classify_dir = output_dir / "classify"
        all_mags_dir = classify_dir / "all_mags"
        all_mags_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy bins (both .fa and .fasta extensions)
        for bin_file in list(Path(binning_result.bins_directory).glob("*.fa")) + \
                         list(Path(binning_result.bins_directory).glob("*.fasta")):
            shutil.copy2(bin_file, all_mags_dir / bin_file.name)
        
        # Copy scMAGs if available
        if scmags_dir:
            for mag_file in list(scmags_dir.glob("*.fa")) + list(scmags_dir.glob("*.fasta")):
                shutil.copy2(mag_file, all_mags_dir / mag_file.name)
        
        classifier = Classifier(
            ClassificationConfig(
                bins_dir=str(all_mags_dir),
                database=config.skani_database,
                metadata=config.skani_metadata,
                threads=config.threads,
                assembler=config.assembler,
                output_dir=str(classify_dir),
                tool=config.classify_tool,
                ass2ref=config.classify_ass2ref,
            )
        )
        classification_result = classifier.run()
        _LOGGER.info("Classification completed: %s", classification_result.deduplicated)
    else:
        _LOGGER.info(
            "Skipping species classification (no skani database provided)"
        )
    
    # ========== STEP 6: Summarize ==========
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 6: Summary and Abundance Profiling")
    _LOGGER.info("=" * 60)
    
    summary_dir = output_dir / "summary"
    
    # Combine all MAGs for summary
    all_mags_for_summary = summary_dir / "all_mags"
    all_mags_for_summary.mkdir(parents=True, exist_ok=True)
    
    # Copy bins (both .fa and .fasta extensions)
    for bin_file in list(Path(binning_result.bins_directory).glob("*.fa")) + \
                     list(Path(binning_result.bins_directory).glob("*.fasta")):
        shutil.copy2(bin_file, all_mags_for_summary / bin_file.name)
    
    # Copy scMAGs if available
    if scmags_dir:
        for mag_file in list(scmags_dir.glob("*.fa")) + list(scmags_dir.glob("*.fasta")):
            shutil.copy2(mag_file, all_mags_for_summary / mag_file.name)
    
    summary_result = process_files(
        quality_report,
        str(summary_dir),
        classification=classification_result.deduplicated if classification_result else None,
        mag_path=str(all_mags_for_summary),
        scmag_info=str(scmags_info) if scmags_info else None,
        fastq_file=clean_fastq,
        threads=config.threads,
    )
    _LOGGER.info("Summary written to %s", summary_result)
    
    # Track sylph intermediate files for cleanup
    tmp_dir = summary_dir / "tmp"
    if tmp_dir.exists():
        intermediate_files.append(tmp_dir / "mag_file_list.txt")
        intermediate_files.append(tmp_dir / "sylph_mag_sketch")
        # Note: Keep sylph_mag_sketch.syldb as it's the final database
    
    # ========== STEP 7: Cleanup Intermediate Files ==========
    if config.clean_intermediate_files:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 7: Cleaning up intermediate files")
        _LOGGER.info("=" * 60)
        
        for file_path in intermediate_files:
            if file_path.exists():
                if file_path.is_file():
                    _LOGGER.info("Removing intermediate file: %s", file_path)
                    file_path.unlink()
                elif file_path.is_dir():
                    _LOGGER.info("Removing intermediate directory: %s", file_path)
                    shutil.rmtree(file_path)
        
        _LOGGER.info("Intermediate file cleanup completed")
    else:
        _LOGGER.info("Intermediate files preserved (--keep-intermediate-files was used)")
    
    # ========== Pipeline Complete ==========
    _LOGGER.info("=" * 60)
    _LOGGER.info("PIPELINE COMPLETED SUCCESSFULLY")
    _LOGGER.info("=" * 60)
    _LOGGER.info("Output directory: %s", output_dir)
    _LOGGER.info("Summary: %s", summary_result)
