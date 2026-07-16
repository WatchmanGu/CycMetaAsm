"""
Wrapped assembly pipeline including assembly and optional polishing.
The raw assembly is performed using myloasm (default) or metaFlye for long-read metagenomic data, followed by optional polishing
using NextPolish with long reads and optional short reads.
Raw assembly 'assembly.fasta' in the assembly directory, polishing results 'genome.nextpolish.fasta' in the 'polish' subdirectory.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from ..utils import checkpoint, mark_done, run_cmd

_LOGGER = logging.getLogger(__name__)


@dataclass
class AssemblyConfig:
    """
    Configuration for the assembly pipeline.
    Attributes:
        fastq_path (str): Path to the FASTQ input files.
        output_dir (str): Directory where assembly results will be stored.
        assembler (str): Assembler to use (e.g., 'spades').
        threads (int): Number of threads to allocate to the assembly.
        preset (Optional[str]): Optional preset to pass to the assembler.
        polish (bool): Whether to run the optional polishing step.
        polish_dir (Optional[str]): Directory where polishing results will be stored.
        short_reads1 (Optional[str]): Path to the paired short reads file (forward).
        short_reads2 (Optional[str]): Path to the paired short reads file (reverse).
        myloasm_path (str): Executable name or path for myloasm.
        nextpolish_path (str): Executable name or path for NextPolish.
    """

    fastq_path: Path
    output_dir: Path
    assembler: str
    threads: int
    polish_dir: Optional[Path]
    preset: Optional[str] = None
    polish: bool = False
    short_reads1: Optional[Path] = None
    short_reads2: Optional[Path] = None
    myloasm_path: str = "myloasm"
    nextpolish_path: str = "nextPolish"


@dataclass
class AssemblyResult:
    """
    Attributes:
        assembly_fasta_path (str): Path to the assembled FASTA file.
        assembly_info (Optional[str]): Optional path to assembly information file.
        assembly_dir (str): Directory where assembly results are stored.
    """

    fasta_path: str
    output_dir: Optional[str]
    assembly_info: str


class AssemblyRunner:
    def __init__(self, config: AssemblyConfig) -> None:
        self.config = config
        self.assembly_dir = config.output_dir
        self.assembly_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> AssemblyResult:
        """
        Run the assembly pipeline.
        Returns:
        AssemblyResult: The result of the assembly and polishing (if applicable).
        Includes paths to the assembled FASTA file (will be the polished fasta if enabled), assembly work directory and assembly info.
        """
        fasta_path, assembly_info = self._run_assembler()
        if self.config.polish:
            fasta_path = self._run_polish(fasta_path)
        return AssemblyResult(
            str(fasta_path), str(self.assembly_dir), str(assembly_info)
        )

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------
    def _run_assembler(self) -> Tuple[Path, Path]:
        if checkpoint(self.assembly_dir):
            _LOGGER.info("Assembly already completed for %s", self.config.assembler)
            return self._assembly_output_paths()

        assembler = self.config.assembler.lower()
        if assembler == "myloasm":
            self._run_myloasm()
        elif assembler == "metaflye":
            self._run_metaflye()
        else:
            raise ValueError(f"Unsupported assembler: {self.config.assembler}")
        mark_done(self.assembly_dir)
        return self._assembly_output_paths()

    def _run_myloasm(self) -> None:
        """Run myloasm and standardize its FASTA output name."""
        cmd = [
            self.config.myloasm_path,
            str(self.config.fastq_path),
            "-o",
            str(self.assembly_dir),
            "-t",
            str(self.config.threads),
        ]
        _LOGGER.info("Running myloasm on %s", self.config.fastq_path)
        run_cmd(cmd)
        self._standardize_myloasm_output()

    def _standardize_myloasm_output(self) -> Path:
        target = self.assembly_dir / "assembly.fasta"
        candidates = [
            target,
            self.assembly_dir / "assembly_primary.fa",
        ]
        for candidate in candidates:
            if not candidate.exists():
                continue
            if candidate.resolve() != target.resolve():
                shutil.copy2(candidate, target)
            return target
        raise FileNotFoundError(
            "myloasm completed but no assembly FASTA was found. "
            f"Checked: {', '.join(str(path) for path in candidates)}"
        )

    def _run_metaflye(self) -> None:
        """
        Run metaFlye assembler for long-read metagenomic sequencing.
        """
        cmd = [
            "flye",
            *(self.config.preset.split() if self.config.preset else []),
            str(self.config.fastq_path),
            "--out-dir",
            str(self.assembly_dir),
            "--threads",
            str(self.config.threads),
            "--meta",
        ]
        _LOGGER.info("Running metaFlye on %s", self.config.fastq_path)
        run_cmd(cmd)

    def _assembly_output_paths(self) -> Tuple[Path, Path]:
        assembler = self.config.assembler.lower()
        if assembler == "metaflye":
            return (
                self.assembly_dir / "assembly.fasta",
                self.assembly_dir / "assembly_info.txt",
            )
        if assembler == "myloasm":
            fasta_path = self.assembly_dir / "assembly.fasta"
            return fasta_path, fasta_path
        raise ValueError(f"Unsupported assembler: {self.config.assembler}")

    # ------------------------------------------------------------------
    # Polishing
    # ------------------------------------------------------------------
    def _run_polish(self, genome_path: Path) -> Path:
        polish_dir = self.config.polish_dir
        polish_dir.mkdir(parents=True, exist_ok=True)
        if checkpoint(polish_dir):
            _LOGGER.info("Polishing already completed for %s", genome_path)
            return polish_dir / "genome.nextpolish.fasta"

        lgs_fofn_path = self._write_fofn(
            polish_dir / "lgs.fofn",
            [self.config.fastq_path],
        )
        if self.config.short_reads1 and self.config.short_reads2:
            filtered = self._filter_short_reads(polish_dir)
            sgs_fofn_path = self._write_fofn(polish_dir / "sgs.fofn", filtered)
        else:
            sgs_fofn_path = None
        run_cfg = self._write_run_cfg(
            polish_dir, genome_path, lgs_fofn_path, sgs_fofn_path
        )
        run_cmd((str(self.config.nextpolish_path), str(run_cfg)))
        mark_done(polish_dir)
        return polish_dir / "genome.nextpolish.fasta"

    def _filter_short_reads(self, polish_dir: Path) -> Tuple[Path, Path]:
        """
        Filter short reads using fastp.
        Done within the short_reads_qc subdirectory of the polishing directory.
        Returns:
            Tuple[str, str]: Paths to the filtered short reads (R1, R2).
        """
        qc_dir = polish_dir / "short_reads_qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        if checkpoint(qc_dir):
            _LOGGER.info("Short-read filtering already completed")
            r1 = qc_dir / "filter_1.fq.gz"
            r2 = qc_dir / "filter_2.fq.gz"
            return r1, r2

        cmd = (
            "fastp",
            "-i",
            str(self.config.short_reads1),
            "-o",
            str(qc_dir / "filter_1.fq.gz"),
            "-I",
            str(self.config.short_reads2),
            "-O",
            str(qc_dir / "filter_2.fq.gz"),
            "--n_base_limit",
            "0",
            "--thread",
            str(self.config.threads),
        )
        run_cmd(cmd)
        mark_done(qc_dir)
        return qc_dir / "filter_1.fq.gz", qc_dir / "filter_2.fq.gz"

    def _write_fofn(self, fofn_path: Path, entries: Iterable[Path]) -> Path:
        with fofn_path.open("w") as handle:
            for entry in entries:
                handle.write(f"{entry.resolve()!s}\n")
        return fofn_path

    def _write_run_cfg(
        self,
        polish_dir: Path,
        genome_path: Path,
        lgs_fofn: Path,
        sgs_fofn: Optional[Path],
    ) -> str:
        run_cfg = polish_dir / "run.cfg"
        has_sgs = sgs_fofn is not None
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
genome = {genome_path.resolve()}
genome_size = auto
workdir = {polish_dir.resolve()}
polish_options = -p {{multithread_jobs}}

{sgs_section}
[lgs_option]
lgs_fofn = {lgs_fofn.resolve()}
lgs_options = -min_read_len 1000 -max_depth 100
lgs_minimap2_options = -x map-ont
"""
        with run_cfg.open("w") as handle:
            handle.write(content)
        return run_cfg
