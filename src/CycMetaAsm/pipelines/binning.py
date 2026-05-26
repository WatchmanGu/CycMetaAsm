"""Binning pipeline wrapping LorBin and SemiBin2."""

from __future__ import annotations

import logging
import shutil
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
    binner: str = "lorbin"
    lorbin_path: str = "LorBin"
    binning_tool: str = "SemiBin2"
    binning_mode: str = "global"


@dataclass
class BinningResult:
    bins_directory: str
    alignment_bam: str


def run_binning(config: BinningConfig) -> BinningResult:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    binner = config.binner.lower()
    if binner not in {"lorbin", "semibin2"}:
        raise ValueError(f"Unsupported binner: {config.binner}")

    if checkpoint(output_dir):
        _LOGGER.info("Binning already completed for %s with %s", config.assembler, binner)
        return BinningResult(
            str(output_dir / "output_bins"), str(output_dir / "aligned.bam")
        )

    clear_directory(output_dir)
    aligned_bam = _align_reads(config, output_dir)

    if binner == "lorbin":
        _run_lorbin(config, output_dir, aligned_bam)
    else:
        _run_semibin2(config, output_dir, aligned_bam)

    mark_done(output_dir)
    return BinningResult(str(output_dir / "output_bins"), str(aligned_bam))


def _align_reads(config: BinningConfig, output_dir: Path) -> Path:
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
    return aligned_bam


def _run_semibin2(config: BinningConfig, output_dir: Path, aligned_bam: Path) -> None:
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


def _run_lorbin(config: BinningConfig, output_dir: Path, aligned_bam: Path) -> None:
    bin_cmd = [
        config.lorbin_path,
        "bin",
        "--fasta",
        config.assembly_fasta,
        "--output",
        str(output_dir),
        "--num_process",
        str(config.threads),
        "--bam",
        str(aligned_bam),
    ]
    _LOGGER.info("Running LorBin")
    run_cmd(bin_cmd)
    _standardize_lorbin_bins(output_dir)


def _standardize_lorbin_bins(output_dir: Path) -> Path:
    bins_dir = output_dir / "output_bins"
    bins_dir.mkdir(parents=True, exist_ok=True)

    patterns = (
        "bin.*.fa",
        "bin.*.fasta",
        "bin*.fa",
        "bin*.fasta",
        "Bin*.fa",
        "Bin*.fasta",
        "*.fa",
        "*.fasta",
    )
    candidates: list[Path] = []
    seen: set[Path] = set()
    for search_dir in (bins_dir, output_dir):
        for pattern in patterns:
            for candidate in sorted(search_dir.glob(pattern)):
                if not candidate.is_file():
                    continue
                resolved = candidate.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(candidate)

    if not candidates:
        raise FileNotFoundError(
            f"LorBin completed but no FASTA bins were found under {output_dir}"
        )

    existing_fa = [path for path in candidates if path.parent == bins_dir and path.suffix == ".fa"]
    if existing_fa:
        return bins_dir

    for index, candidate in enumerate(candidates, start=1):
        target = bins_dir / f"LorBin_{index}.fa"
        if candidate.resolve() == target.resolve():
            continue
        shutil.copy2(candidate, target)
    return bins_dir
