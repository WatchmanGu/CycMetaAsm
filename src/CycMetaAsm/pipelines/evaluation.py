"""Evaluation utilities wrapping metaQUAST and CheckM2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional

from Bio import SeqIO

from ..utils import checkpoint, mark_done, myopen, read_assembly_info, run_cmd

_LOGGER = logging.getLogger(__name__)


def _normalise_circular(value: str) -> str:
    return "yes" if value.strip().lower() in {"yes", "y"} else "no"


@dataclass
class EvaluationConfig:
    assembly_fasta: str
    output_dir: str
    assembler: str
    threads: int = 10
    assembly_info: Optional[str] = None
    database_path: Optional[str] = None
    reference: Optional[str] = None


class ContigAnalyzer:
    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config
        self.evaluation_dir = Path(config.output_dir)
        self.evaluation_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def get_contig_info(self) -> Mapping[str, Mapping[str, str]]:
        contigs = self._parse_contigs()
        if contigs:
            self._assess_from_checkm2_large_contigs(contigs)
        if self.config.assembly_info:
            self._assess_from_assembly_info(contigs)
        return contigs

    def run_metaquast(
        self, fasta_paths: Optional[Iterable[str]] = None, *, min_contig: int = 1000
    ) -> str:
        output_dir = self.evaluation_dir / "quast"
        if checkpoint(output_dir):
            _LOGGER.info("metaQUAST already executed for %s", self.config.assembler)
            return str(output_dir)
        cmd = [
            "metaquast",
            "--min-contig",
            str(min_contig),
            "--threads",
            str(self.config.threads),
            "--silent",
            "-o",
            str(output_dir),
        ]
        if self.config.reference:
            cmd.extend(["--reference", self.config.reference])
        inputs = list(fasta_paths) if fasta_paths else [self.config.assembly_fasta]
        cmd.extend(inputs)
        run_cmd(cmd)
        mark_done(output_dir)
        return str(output_dir)

    def run_checkm2(self, fasta_path: Optional[str] = None) -> str:
        output_dir = self.evaluation_dir / "checkm2"
        quality_report = output_dir / "quality_report.tsv"
        if checkpoint(output_dir):
            _LOGGER.info("CheckM2 already executed for %s", self.config.assembler)
            return str(quality_report)
        if not self.config.database_path:
            raise ValueError("database_path is required for CheckM2")
        checkm2_db = Path(self.config.database_path)
        fasta_input = fasta_path or self.config.assembly_fasta
        cmd = [
            "checkm2",
            "predict",
            "--threads",
            str(self.config.threads),
            "--input",
            fasta_input,
            "--output-directory",
            str(output_dir),
            "--force",
            "--quiet",
            "--database_path",
            str(checkm2_db),
        ]
        if Path(fasta_input).is_dir():
            for candidate in Path(fasta_input).iterdir():
                ext = candidate.suffix.lstrip(".")
                if ext:
                    cmd.extend(["-x", ext])
                    break
        run_cmd(cmd)
        mark_done(output_dir)
        return str(quality_report)

    # ------------------------------------------------------------------
    # CheckM2 assessment helpers
    # ------------------------------------------------------------------
    def _parse_contigs(self) -> MutableMapping[str, MutableMapping[str, str]]:
        """
        Return a mapping of contig IDs to their properties.
        Returns:
            MutableMapping[str, MutableMapping[str, str]]: A mapping where each key is a
            contig ID and the value is another mapping containing properties like Length,
            Completeness, Contamination, Coverage, and Circular.
        Completeness , Contamination, Coverage, and Circular are set to 'NA' by default and can be updated later.
        """
        contigs: MutableMapping[str, MutableMapping[str, str]] = {}
        self.tmp_dir = self.evaluation_dir / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        with myopen(self.config.assembly_fasta) as handle:
            for record in SeqIO.parse(handle, "fasta"):
                contig_id = record.description.split()[0]
                length = len(record.seq)
                contigs[contig_id] = {
                    "Length": str(length),
                    "Completeness": "NA",
                    "Contamination": "NA",
                    "Coverage": "NA",
                    "Circular": "NA",
                }
                if length >= 500_000:
                    SeqIO.write(
                        record, str(self.tmp_dir / f"{contig_id}.fasta"), "fasta"
                    )
        return contigs

    def _assess_from_checkm2_large_contigs(
        self, contigs: MutableMapping[str, MutableMapping[str, str]]
    ) -> None:
        """
        Get the assessment from CheckM2 for contigs larger than 500kb.
        """
        if not any(self.tmp_dir.iterdir()):
            return
        if not self.config.database_path:
            _LOGGER.warning("CheckM2 skipped: database path not provided")
            return
        quality_report = self.run_checkm2(str(self.tmp_dir))
        with myopen(quality_report) as handle:
            next(handle, None)
            for line in handle:
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                contig_id, completeness, contamination = parts[:3]
                if contig_id in contigs:
                    contigs[contig_id]["Completeness"] = completeness
                    contigs[contig_id]["Contamination"] = contamination

    def _assess_from_assembly_info(
        self, contigs: MutableMapping[str, MutableMapping[str, str]]
    ) -> None:
        """
        Get the assessment from assembly information file (generated by MetaFlye) to update contig properties.
        Parameters:
        contigs (MutableMapping[str, MutableMapping[str, str]]): The contig information mapping to update.
        """
        info = read_assembly_info(self.config.assembly_info)
        for contig_id, values in info.items():
            if contig_id not in contigs or f"{contig_id}_np1212" not in contigs:
                continue
            elif contig_id in contigs:
                if "coverage" in values:
                    contigs[contig_id]["Coverage"] = values["coverage"]
                if "circular" in values:
                    contigs[contig_id]["Circular"] = _normalise_circular(
                        values["circular"]
                    )
            elif f"{contig_id}_np1212" in contigs:
                # TODO: Could deal with polished contig IDs yet. But not sure a normal case.
                if "coverage" in values:
                    contigs[f"{contig_id}_np1212"]["Coverage"] = values["coverage"]
                if "circular" in values:
                    contigs[f"{contig_id}_np1212"]["Circular"] = _normalise_circular(
                        values["circular"]
                    )
