"""Assembly pipeline wrapping metaFlye and metaMDBG."""

from __future__ import annotations

import gzip
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ..utils import checkpoint, mark_done, run_cmd

_LOGGER = logging.getLogger(__name__)


@dataclass
class AssemblyConfig:
    fastq_path: str
    output_dir: str
    assembler: str
    threads: int
    preset: Optional[str] = None
    polish: bool = False
    short_reads1: Optional[str] = None
    short_reads2: Optional[str] = None
    nextpolish_path: str = "nextPolish"


@dataclass
class AssemblyResult:
    fasta_path: str
    assembly_info: Optional[str]
    output_dir: str


class AssemblyRunner:
    def __init__(self, config: AssemblyConfig) -> None:
        self.config = config
        self.assembly_dir = Path(config.output_dir) / "Assembly" / config.assembler
        self.assembly_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> AssemblyResult:
        fasta_path, assembly_info = self._run_assembler()
        if self.config.polish:
            fasta_path = self._run_polish(fasta_path)
        return AssemblyResult(str(fasta_path), assembly_info, str(self.assembly_dir))

    # ------------------------------------------------------------------
    # Assembly execution
    # ------------------------------------------------------------------
    def _run_assembler(self) -> Tuple[Path, Optional[str]]:
        if checkpoint(self.assembly_dir):
            _LOGGER.info("Assembly already completed for %s", self.config.assembler)
            return self._output_paths()

        assembler = self.config.assembler.lower()
        if assembler == "metaflye":
            self._run_metaflye()
        elif assembler == "metamdbg":
            self._run_mdbg()
        else:
            raise ValueError(f"Unsupported assembler: {self.config.assembler}")
        mark_done(self.assembly_dir)
        return self._output_paths()

    def _run_metaflye(self) -> None:
        cmd = [
            "flye",
            *(self.config.preset.split() if self.config.preset else []),
            self.config.fastq_path,
            "--out-dir",
            str(self.assembly_dir),
            "--threads",
            str(self.config.threads),
            "--meta",
        ]
        _LOGGER.info("Running metaFlye on %s", self.config.fastq_path)
        run_cmd(cmd)

    def _run_mdbg(self) -> None:
        cmd = [
            "metaMDBG",
            "asm",
            *(self.config.preset.split() if self.config.preset else []),
            self.config.fastq_path,
            "--out-dir",
            str(self.assembly_dir),
            "--threads",
            str(self.config.threads),
        ]
        _LOGGER.info("Running metaMDBG on %s", self.config.fastq_path)
        run_cmd(cmd)

        gz_path = self.assembly_dir / "contigs.fasta.gz"
        fasta_path = self.assembly_dir / "assembly.fasta"
        with gzip.open(gz_path, "rt") as handle_in, fasta_path.open("wt") as handle_out:
            shutil.copyfileobj(handle_in, handle_out)

    def _output_paths(self) -> Tuple[Path, Optional[str]]:
        assembler = self.config.assembler.lower()
        if assembler == "metaflye":
            return (
                self.assembly_dir / "assembly.fasta",
                str(self.assembly_dir / "assembly_info.txt"),
            )
        fasta_path = self.assembly_dir / "assembly.fasta"
        return fasta_path, str(fasta_path)

    # ------------------------------------------------------------------
    # Polishing
    # ------------------------------------------------------------------
    def _run_polish(self, genome_path: Path) -> Path:
        polish_dir = self.assembly_dir / "polish"
        polish_dir.mkdir(parents=True, exist_ok=True)
        if checkpoint(polish_dir):
            _LOGGER.info("Polishing already completed for %s", genome_path)
            return polish_dir / "genome.nextpolish.fasta"

        self._write_fofn(
            polish_dir.parent / "lgs.fofn",
            [self.config.fastq_path],
        )
        if self.config.short_reads1 and self.config.short_reads2:
            filtered = self._filter_short_reads(polish_dir)
            self._write_fofn(polish_dir.parent / "sgs.fofn", filtered)

        run_cfg = self._write_run_cfg(genome_path)
        run_cmd((self.config.nextpolish_path, run_cfg))
        mark_done(polish_dir)
        return polish_dir / "genome.nextpolish.fasta"

    def _filter_short_reads(self, polish_dir: Path) -> Tuple[str, str]:
        qc_dir = polish_dir.parent / "qc" / "short_reads"
        qc_dir.mkdir(parents=True, exist_ok=True)
        if checkpoint(qc_dir):
            _LOGGER.info("Short-read filtering already completed")
            r1 = qc_dir / "filter_1.fq.gz"
            r2 = qc_dir / "filter_2.fq.gz"
            return str(r1), str(r2)

        cmd = (
            "fastp",
            "-i",
            self.config.short_reads1,
            "-o",
            str(qc_dir / "filter_1.fq.gz"),
            "-I",
            self.config.short_reads2,
            "-O",
            str(qc_dir / "filter_2.fq.gz"),
            "--n_base_limit",
            "0",
            "--thread",
            str(self.config.threads),
        )
        run_cmd(cmd)
        mark_done(qc_dir)
        return str(qc_dir / "filter_1.fq.gz"), str(qc_dir / "filter_2.fq.gz")

    def _write_fofn(self, fofn_path: Path, entries: list[str]) -> None:
        with fofn_path.open("w") as handle:
            for entry in entries:
                handle.write(f"{Path(entry).resolve()!s}\n")

    def _write_run_cfg(self, genome_path: Path) -> str:
        run_cfg = self.assembly_dir / "run.cfg"
        lgs_fofn = self.assembly_dir / "lgs.fofn"
        sgs_fofn = self.assembly_dir / "sgs.fofn"
        has_sgs = sgs_fofn.exists() and sgs_fofn.stat().st_size > 0
        sgs_section = ""
        if has_sgs:
            sgs_section = (
                """
[sgs_option]
sgs_fofn = {sgs}
sgs_options = -max_depth 100 -bwa
"""
            ).format(sgs=sgs_fofn.resolve())

        content = f"""[General]
job_type = local
job_prefix = nextPolish
task = best
rewrite = yes
deltmp = yes
rerun = 3
parallel_jobs = 6
multithread_jobs = {self.config.threads}
genome = {Path(genome_path).resolve()}
genome_size = auto
workdir = {self.assembly_dir.resolve()}/polish
polish_options = -p {{multithread_jobs}}

{sgs_section}
[lgs_option]
lgs_fofn = {lgs_fofn.resolve()}
lgs_options = -min_read_len 1000 -max_depth 100
lgs_minimap2_options = -x map-ont
"""
        with run_cfg.open("w") as handle:
            handle.write(content)
        return str(run_cfg)
