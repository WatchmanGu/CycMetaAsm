"""Bin classification helpers using skani or kMetaShot."""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

import pandas as pd

from ..utils import checkpoint, mark_done, run_cmd

_LOGGER = logging.getLogger(__name__)


def _file_md5(path: str, chunk_size: int = 8192) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_taxonomy(taxonomy: Optional[str]) -> Mapping[str, str]:
    levels = {
        k: ""
        for k in ("Domain", "Phylum", "Class", "Order", "Family", "Genus", "Species")
    }
    if not taxonomy:
        return levels
    for part in taxonomy.split(";"):
        if "__" not in part:
            continue
        prefix, name = part.split("__", 1)
        key = {
            "d": "Domain",
            "p": "Phylum",
            "c": "Class",
            "o": "Order",
            "f": "Family",
            "g": "Genus",
            "s": "Species",
        }.get(prefix.lower())
        if key:
            levels[key] = name
    return levels


def _extract_accession(path: str) -> str:
    filename = Path(path).name
    match = re.search(r"(GC[AF]_\d+\.\d+)", filename)
    return match.group(1) if match else filename


def _extract_bin_name(path: str) -> str:
    return Path(path).stem


@dataclass
class ClassificationConfig:
    bins_dir: str
    database: str
    metadata: str
    threads: int
    assembler: str
    output_dir: str
    tool: str = "skani"
    ass2ref: float = 0.5


@dataclass
class ClassificationResult:
    full: str
    deduplicated: str


class Classifier:
    def __init__(self, config: ClassificationConfig) -> None:
        self.config = config
        self.classify_dir = Path(config.output_dir) / "classify" / self.config.assembler

    def run(self) -> ClassificationResult:
        self.classify_dir.mkdir(parents=True, exist_ok=True)
        if self.config.tool.lower().startswith("skani"):
            return self._run_skani()
        if "kmetashot" in self.config.tool.lower():
            return self._run_skani()
        #     return self._run_kmetashot()
        raise ValueError(f"Unsupported classification tool: {self.config.tool}")

    # ------------------------------------------------------------------
    # skani
    # ------------------------------------------------------------------
    def _run_skani(self) -> ClassificationResult:
        result = self.classify_dir / "classify_result.tsv"
        dedup = self.classify_dir / "classify_result_deduplicated.tsv"
        if checkpoint(self.classify_dir):
            _LOGGER.info("skani classification already completed")
            return ClassificationResult(str(result), str(dedup))

        bins = list(Path(self.config.bins_dir).glob("*"))
        if not bins:
            raise FileNotFoundError(f"No bins found under {self.config.bins_dir}")

        metadata = self._load_gtdb_metadata()
        cmd = [
            self.config.tool,
            "search",
            *[str(bin_path) for bin_path in bins],
            "-d",
            str(Path(self.config.database)),
            "-o",
            str(self.classify_dir / "results_file.txt"),
            "-t",
            str(self.config.threads),
            "--min-af",
            "50",  # Only classify bins with at least 50% ref alignment fraction,refer to GTDB
            "--short-header",
            "--detailed",
        ]
        run_cmd(cmd)
        self._parse_skani_results(metadata)
        mark_done(self.classify_dir)
        return ClassificationResult(str(result), str(dedup))

    def _load_gtdb_metadata(self) -> Mapping[str, str]:
        metadata_file = Path(self.config.metadata)
        if not metadata_file.exists():
            raise FileNotFoundError(f"GTDB metadata not found at {metadata_file}")
        cache_path = metadata_file.with_suffix(metadata_file.suffix + ".pkl")
        md5sum = _file_md5(str(metadata_file))

        if cache_path.exists():
            try:
                with cache_path.open("rb") as handle:
                    cached = pickle.load(handle)
                if cached.get("__md5__") == md5sum:
                    return cached["data"]
            except Exception as exc:  # pragma: no cover - cache load best-effort
                _LOGGER.warning("Failed to load metadata cache: %s", exc)

        taxonomy: Dict[str, str] = {}
        with metadata_file.open() as handle:
            for line in handle:
                accession, tax = line.strip().split("\t", 1)
                taxonomy[accession] = tax
        try:
            with cache_path.open("wb") as handle:
                pickle.dump({"__md5__": md5sum, "data": taxonomy}, handle)
        except Exception as exc:  # pragma: no cover - cache write best-effort
            _LOGGER.warning("Failed to write metadata cache: %s", exc)
        return taxonomy

    def _parse_skani_results(self, metadata: Mapping[str, str]) -> None:
        csv_file = self.classify_dir / "results_file.txt"
        df = pd.read_csv(csv_file, sep="\t")
        # Avoid chained assignment by using .rename and .loc consistently
        df = df.rename(columns={col: col.lower() for col in df.columns})
        df.loc[:, "ref_name"] = df["ref_file"].map(_extract_accession)
        df.loc[:, "query_name"] = df["query_file"].map(_extract_bin_name)
        df.loc[:, "taxonomy"] = df["ref_name"].map(metadata.get)
        taxonomy_expanded = df["taxonomy"].apply(_parse_taxonomy).apply(pd.Series)
        final_df = pd.concat(
            [
                df[["ref_name", "query_name", "ani", "num_query_contigs", "taxonomy"]],
                taxonomy_expanded,
            ],
            axis=1,
        ).rename(
            columns={
                "ref_name": "Reference",
                "query_name": "MAG_ID",
                "ani": "ANI",
                "num_query_contigs": "Num_contigs",
                "taxonomy": "Taxonomy",
            }
        )
        # dedup_df = final_df.sort_values("ANI", ascending=False).drop_duplicates(
        #     "MAG_ID", keep="first"
        # )
        # The raw skani results are sorted by ANI already, so just drop duplicates
        dedup_df = final_df.drop_duplicates("MAG_ID", keep="first")
        result = self.classify_dir / "classify_result.tsv"
        dedup = self.classify_dir / "classify_result_deduplicated.tsv"
        final_df.to_csv(result, sep="\t", index=False)
        dedup_df.to_csv(dedup, sep="\t", index=False)

    # ------------------------------------------------------------------
    # kMetaShot
    # ------------------------------------------------------------------
    # @DeprecationWarning
    # def _run_kmetashot(self) -> ClassificationResult:
    #     result = self.classify_dir / "classify_result.tsv"
    #     dedup = self.classify_dir / "classify_result_deduplicated.tsv"
    #     if checkpoint(self.classify_dir):
    #         _LOGGER.info("kMetaShot classification already completed")
    #         return ClassificationResult(str(result), str(dedup))

    #     cmd = [
    #         self.config.tool,
    #         "--bins_dir",
    #         self.config.bins_dir,
    #         "--reference",
    #         str(
    #             Path(self.config.database_root)
    #             / "kMetaShot_db"
    #             / "kMetaShot_reference.h5"
    #         ),
    #         "--ass2ref",
    #         str(self.config.ass2ref),
    #         "--processes",
    #         str(self.config.threads),
    #         "--out_dir",
    #         str(self.classify_dir),
    #     ]
    #     run_cmd(cmd)
    #     mark_done(self.classify_dir)
    #     return ClassificationResult(str(result), str(dedup))
