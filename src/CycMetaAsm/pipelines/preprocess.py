"""Preprocessing steps: downsampling, filtering, host removal."""

from __future__ import annotations

import logging
import os
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from Bio import SeqIO

from ..utils import checkpoint, mark_done, myopen, run_cmd

_LOGGER = logging.getLogger(__name__)


def _format_size_units(size_bp: int) -> str:
    if size_bp >= 10**9:
        return f"{size_bp // 10**9}Gb"
    if size_bp >= 10**6:
        return f"{size_bp // 10**6}Mb"
    if size_bp >= 10**3:
        return f"{size_bp // 10**3}Kb"
    return f"{size_bp}bp"


@dataclass
class DownsampleResult:
    directory: str
    fastq_path: str


@dataclass
class FastqDownsampler:
    fastq_path: str
    output_root: str
    threads: int = 4
    seed: int = 1005

    def __post_init__(self) -> None:
        Path(self.output_root).mkdir(parents=True, exist_ok=True)

    def downsample(self, target_bases: int) -> DownsampleResult:
        # size_str = _format_size_units(target_bases)
        # work_dir = Path(self.output_root) / size_str
        work_dir = Path(self.output_root)
        work_dir.mkdir(parents=True, exist_ok=True)

        fastq_out = work_dir / "downsampled.fastq"
        fastq_out_gz = fastq_out.with_suffix(fastq_out.suffix + ".gz")

        if checkpoint(work_dir):
            _LOGGER.info("Downsample output already exists at %s", fastq_out_gz)
            return DownsampleResult(str(work_dir), str(fastq_out_gz))

        read_lengths = self._load_read_lengths()
        total_available = sum(length for _, length in read_lengths)
        if total_available <= target_bases:
            _LOGGER.warning(
                "Not enough bases (%s bp), copying original file.", total_available
            )
            self._copy_to_destination(fastq_out)
            mark_done(work_dir)
            return DownsampleResult(str(work_dir), str(fastq_out_gz))

        selected_indices, total_bases = self._select_reads(read_lengths, target_bases)
        self._write_selected_reads(selected_indices, fastq_out)
        self._compress_output(fastq_out)
        mark_done(work_dir)
        _LOGGER.info("Downsampled %s bp of reads", _format_size_units(total_bases))
        return DownsampleResult(str(work_dir), str(fastq_out_gz))

    def _load_read_lengths(self) -> list[Tuple[int, int]]:
        lengths: list[Tuple[int, int]] = []
        with myopen(self.fastq_path) as handle:
            for idx, record in enumerate(SeqIO.parse(handle, "fastq")):
                lengths.append((idx, len(record.seq)))
        return lengths

    def _select_reads(
        self, read_lengths: list[Tuple[int, int]], target_bases: int
    ) -> Tuple[set[int], int]:
        random.seed(self.seed)
        random.shuffle(read_lengths)
        selected: set[int] = set()
        accumulated = 0
        for idx, length in read_lengths:
            if accumulated + length > target_bases:
                if not selected:
                    selected.add(idx)
                    accumulated += length
                break
            selected.add(idx)
            accumulated += length
        return selected, accumulated

    def _write_selected_reads(
        self, selected_indices: set[int], fastq_out: Path
    ) -> None:
        if not selected_indices:
            shutil.copyfile(self.fastq_path, fastq_out)
            return
        max_index = max(selected_indices)
        with myopen(self.fastq_path) as handle_in, fastq_out.open("wt") as handle_out:
            for idx, record in enumerate(SeqIO.parse(handle_in, "fastq")):
                if idx in selected_indices:
                    SeqIO.write(record, handle_out, "fastq")
                if idx >= max_index:
                    break

    def _compress_output(self, fastq_out: Path) -> None:
        run_cmd(("pigz", "-f", "-p", str(self.threads), str(fastq_out)))

    def _copy_to_destination(self, destination: Path) -> None:
        source = Path(self.fastq_path)
        if source.suffix == ".gz":
            shutil.copyfile(source, str(destination) + ".gz")
        else:
            shutil.copyfile(source, destination)
            self._compress_output(destination)


def filter_fastq(
    fastq_path: str,
    output_dir: str,
    min_length: int,
    min_quality: int,
    threads: int,
    *,
    filter_tool: str = "chopper",
) -> str:
    work_dir = Path(output_dir) / "qc"
    work_dir.mkdir(parents=True, exist_ok=True)
    filtered_fastq = work_dir / "filtered.fastq.gz"
    if checkpoint(work_dir):
        _LOGGER.info("Reads filtering already completed at %s", filtered_fastq)
        return str(filtered_fastq)

    filter_cmd = (
        filter_tool,
        "-i",
        fastq_path,
        "--minlength",
        str(min_length),
        "--quality",
        str(min_quality),
        "-t",
        str(threads),
    )
    pigz_cmd = ("pigz", "-p", str(threads))
    _LOGGER.info("Filtering reads (%s)", fastq_path)
    with filtered_fastq.open("wb") as handle:
        run_cmd([filter_cmd, pigz_cmd], stdout=handle)
    mark_done(work_dir)
    return str(filtered_fastq)


def remove_host(
    fastq_path: str,
    output_dir: str,
    host_reference: str,
    threads: int,
    *,
    minimap2_preset: str,
    minimap2_path: str = "minimap2",
    samtools_path: str = "samtools",
) -> str:
    work_dir = Path(output_dir) / "remove_host"
    work_dir.mkdir(parents=True, exist_ok=True)
    host_removed = work_dir / "host_removed.fastq.gz"
    if checkpoint(work_dir):
        _LOGGER.info("Host removal already completed at %s", host_removed)
        return str(host_removed)

    minimap2_cmd = [
        minimap2_path,
        *[token for token in minimap2_preset.split() if token],
        "-t",
        str(threads),
        host_reference,
        fastq_path,
    ]
    samtools_unmap = (samtools_path, "view", "-@", str(threads), "-f", "4", "-b")
    samtools_bam2fq = (samtools_path, "fastq", "-@", str(threads))
    pigz_cmd = ("pigz", "-p", str(threads))
    with host_removed.open("wb") as handle:
        run_cmd(
            [minimap2_cmd, samtools_unmap, samtools_bam2fq, pigz_cmd], stdout=handle
        )
    mark_done(work_dir)
    return str(host_removed)


@dataclass
class PreprocessResult:
    fastq_path: str
    work_dir: str
    downsampled: bool
    filtered: bool
    host_removed: bool


def run_preprocess(
    fastq_path: str,
    output_dir: str,
    threads: int,
    *,
    downsample_bases: Optional[int] = None,
    min_length: int = 1000,
    min_quality: int = 7,
    host_reference: Optional[str] = None,
    minimap2_preset: Optional[str] = None,
) -> PreprocessResult:
    work_dir = Path(output_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    processed_fastq = fastq_path
    downsampled = False
    if downsample_bases:
        downsample = FastqDownsampler(processed_fastq, str(work_dir), threads)
        result = downsample.downsample(downsample_bases)
        processed_fastq = result.fastq_path
        work_dir = Path(result.directory)
        downsampled = True

    filtered = False
    if min_length and min_quality:
        processed_fastq = filter_fastq(
            processed_fastq, str(work_dir), min_length, min_quality, threads
        )
        filtered = True

    host_removed = False
    if host_reference and minimap2_preset:
        processed_fastq = remove_host(
            processed_fastq,
            str(work_dir),
            host_reference,
            threads,
            minimap2_preset=minimap2_preset,
        )
        host_removed = True

    return PreprocessResult(
        fastq_path=processed_fastq,
        work_dir=str(work_dir),
        downsampled=downsampled,
        filtered=filtered,
        host_removed=host_removed,
    )
