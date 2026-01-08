"""Binning pipeline wrapping SemiBin2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..utils import checkpoint, clear_directory, mark_done, run_cmd

_LOGGER = logging.getLogger(__name__)


@dataclass
class BinningConfig:
    assembly_fasta: str
    reads_path: str
    output_dir: str
    assembler: str
    threads: int
    minimap2_preset: str
    minimap2_path: str = "minimap2"
    samtools_path: str = "samtools"
    binning_tool: str = "SemiBin2"
    binning_mode: str = "global"


@dataclass
class BinningResult:
    bins_directory: str
    alignment_bam: str


def run_binning(config: BinningConfig) -> BinningResult:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if checkpoint(output_dir):
        _LOGGER.info("Binning already completed for %s", config.assembler)
        return BinningResult(
            str(output_dir / "output_bins"), str(output_dir / "aligned.bam")
        )

    clear_directory(output_dir)
    aligned_bam = output_dir / "aligned.bam"
    minimap2_cmd = [
        config.minimap2_path,
        *[token for token in config.minimap2_preset.split() if token],
        "-t",
        str(config.threads),
        "--sam-hit-only",
        config.assembly_fasta,
        config.reads_path,
    ]
    samtools_sort_cmd = (
        config.samtools_path,
        "sort",
        "-@",
        str(config.threads),
        "-o",
        str(aligned_bam),
    )
    _LOGGER.info("Aligning reads to assembly for binning")
    run_cmd([minimap2_cmd, samtools_sort_cmd])
    run_cmd((config.samtools_path, "index", str(aligned_bam)))

    bin_cmd = [
        config.binning_tool,
        "single_easy_bin",
        "--random-seed",
        "1005",
        "--sequencing-type=long_read",
        "--environment",
        config.binning_mode,
        "--compression",
        "none",
        "--tmpdir",
        str(output_dir / "tmp"),
        "-t",
        str(config.threads),
        "--input-fasta",
        config.assembly_fasta,
        "--input-bam",
        str(aligned_bam),
        "--output",
        str(output_dir),
    ]
    _LOGGER.info("Running SemiBin2")
    run_cmd(bin_cmd)
    mark_done(output_dir)
    return BinningResult(str(output_dir / "output_bins"), str(aligned_bam))
