from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "test" / "pipeline_full" / "run_full_pipeline_docker.sh"
DEFAULT_OUTPUT_ROOT = Path("/tmp/opencode/cycmetaasm_full_pipeline_with_dbs")

REQUIRED_PATHS = [
    ROOT / "wdl" / "test" / "sample.fastq.gz",
    Path("/data/gukaijie/project/database/checkm2/CheckM2_database/uniref100.KO.1.dmnd"),
    Path(
        "/data/gukaijie/project/database/NCBI_genome/human/"
        "datasets_GCF_000001405.40/data/GCF_000001405.40/"
        "GCF_000001405.40_GRCh38.p14_genomic.fna"
    ),
    Path("/data/zhouan/Metagenome/metagenome_assembly/database/gtdb/r226/gtdb_r226_ani"),
    Path(
        "/data/zhouan/Metagenome/metagenome_assembly/database/gtdb/r226/"
        "gtdb_r226_ani/metadata.tsv"
    ),
]


class FullPipelineDockerTests(unittest.TestCase):
    def test_required_paths_exist(self) -> None:
        missing = [str(path) for path in REQUIRED_PATHS if not path.exists()]
        self.assertEqual(missing, [])

    def test_runner_is_trackable_and_executable(self) -> None:
        self.assertTrue(SCRIPT.exists())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    @unittest.skipUnless(
        os.environ.get("RUN_CYCMETAASM_FULL_PIPELINE") == "1",
        "Set RUN_CYCMETAASM_FULL_PIPELINE=1 to run the long Docker pipeline test.",
    )
    def test_full_pipeline_docker(self) -> None:
        self.assertIsNotNone(shutil.which("docker"))
        image = os.environ.get("IMAGE", "cycmetaasm:v1.1.0")
        subprocess.run(
            ["docker", "image", "inspect", image],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        env = os.environ.copy()
        env.setdefault("OUTPUT_ROOT", str(DEFAULT_OUTPUT_ROOT))
        env.setdefault("THREADS", "4")
        env.setdefault("POLISH", "1")
        subprocess.run([str(SCRIPT)], cwd=str(ROOT), env=env, check=True)

        output_root = Path(env["OUTPUT_ROOT"])
        output_dir = output_root / "output"
        expected = [
            output_dir / "preprocess" / "remove_host" / "host_removed.fastq.gz",
            output_dir / "assembly" / "assembly.fasta",
            output_dir / "subset_contigs" / "to_be_binned.fasta",
            output_dir / "binning" / "checkm2" / "quality_report.tsv",
            output_dir / "classify" / "classify_result_deduplicated.tsv",
            output_dir / "summary" / "summary.tsv",
            output_dir / "summary" / "quality_stats.tsv",
            output_root / "report" / "raw_rosa" / "raw_QC_results.zip",
            output_root / "report" / "clean_rosa" / "clean_QC_results.zip",
            output_root
            / "report"
            / "final"
            / "sample_CycMetaAsm_Results"
            / "sample_CycMetaAsm_Report.html",
            output_root / "report" / "final" / "sample_CycMetaAsm_Results.zip",
            output_root / "report" / "final" / "summary.txt",
        ]
        missing = [str(path) for path in expected if not path.exists()]
        self.assertEqual(missing, [])

        if env["POLISH"].lower() in {"1", "true"}:
            polish_expected = [
                output_dir / "assembly" / "polish" / "genome.nextpolish.fasta",
                output_dir / "assembly" / "polish" / "_isDone",
                output_dir / "assembly" / "polish" / "run.cfg",
                output_dir / "assembly" / "polish" / "lgs.fofn",
            ]
            missing_polish = [str(path) for path in polish_expected if not path.exists()]
            self.assertEqual(missing_polish, [])

        bins = list((output_dir / "binning" / "output_bins").glob("*.fa"))
        self.assertGreater(len(bins), 0)


if __name__ == "__main__":
    unittest.main()
