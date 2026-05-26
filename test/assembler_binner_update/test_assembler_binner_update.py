from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from CycMetaAsm.cli import build_parser, main  # noqa: E402
from CycMetaAsm.pipelines.assembly import AssemblyConfig, AssemblyRunner  # noqa: E402
from CycMetaAsm.pipelines.binning import _standardize_lorbin_bins  # noqa: E402


class AssemblerBinnerCliTests(unittest.TestCase):
    def test_cli_defaults_to_myloasm_and_lorbin(self) -> None:
        parser = build_parser()

        assemble_args = parser.parse_args(["assemble", "reads.fastq", "out"])
        bin_args = parser.parse_args(["bin", "assembly.fasta", "reads.fastq", "out"])
        pipeline_args = parser.parse_args(
            ["pipeline", "reads.fastq", "out", "--checkm2-db", "checkm2.dmnd"]
        )

        self.assertEqual(assemble_args.assembler, "myloasm")
        self.assertEqual(bin_args.assembler, "myloasm")
        self.assertEqual(bin_args.binner, "lorbin")
        self.assertEqual(pipeline_args.assembler, "myloasm")
        self.assertEqual(pipeline_args.binner, "lorbin")

    def test_metamdbg_is_not_exposed(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["assemble", "reads.fastq", "out", "--assembler", "metamdbg"]
            )

    def test_myloasm_silently_ignores_preset(self) -> None:
        captured = {}

        class FakeRunner:
            def __init__(self, config: AssemblyConfig) -> None:
                captured["config"] = config

            def run(self) -> SimpleNamespace:
                config = captured["config"]
                fasta_path = Path(config.output_dir) / "assembly.fasta"
                fasta_path.parent.mkdir(parents=True, exist_ok=True)
                fasta_path.write_text(">contig1\nACGT\n")
                return SimpleNamespace(
                    fasta_path=str(fasta_path),
                    output_dir=str(config.output_dir),
                    assembly_info=str(fasta_path),
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reads = tmp / "reads.fastq"
            reads.write_text("@read1\nACGT\n+\nIIII\n")
            output = tmp / "out"

            with patch("CycMetaAsm.cli.AssemblyRunner", FakeRunner):
                main(
                    [
                        "assemble",
                        str(reads),
                        str(output),
                        "--assembler",
                        "myloasm",
                        "--preset",
                        "custom-preset",
                    ]
                )

        self.assertIsNone(captured["config"].preset)


class AssemblyAndBinningNormalizationTests(unittest.TestCase):
    def test_myloasm_output_is_standardized_to_assembly_fasta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reads = tmp / "reads.fastq"
            reads.write_text("@read1\nACGT\n+\nIIII\n")
            assembly_dir = tmp / "assembly"
            assembly_dir.mkdir()
            (assembly_dir / "assembly_primary.fa").write_text(">contig1\nACGT\n")

            config = AssemblyConfig(
                fastq_path=reads,
                output_dir=assembly_dir,
                assembler="myloasm",
                threads=2,
                polish_dir=None,
            )
            target = AssemblyRunner(config)._standardize_myloasm_output()

            self.assertEqual(target, assembly_dir / "assembly.fasta")
            self.assertEqual(target.read_text(), ">contig1\nACGT\n")

    def test_lorbin_bins_are_standardized_under_output_bins(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "binning"
            output_dir.mkdir()
            (output_dir / "bin.1.fasta").write_text(">bin1\nACGT\n")

            bins_dir = _standardize_lorbin_bins(output_dir)

            self.assertEqual(bins_dir, output_dir / "output_bins")
            self.assertEqual(
                (bins_dir / "LorBin_1.fa").read_text(),
                ">bin1\nACGT\n",
            )


class WdlStaticTests(unittest.TestCase):
    def test_wdl_uses_single_cycmetaasm_image_tag(self) -> None:
        tags = []
        for path in (ROOT / "wdl").glob("**/*.wdl"):
            tags.extend(re.findall(r'docker:\s*"([^"]+)"', path.read_text()))

        self.assertTrue(tags)
        self.assertEqual(set(tags), {"cycmetaasm:v1.1.0"})

    def test_wdl_exposes_binner_and_generalized_bin_glob(self) -> None:
        workflow = (ROOT / "wdl" / "workflow.wdl").read_text()
        bin_task = (ROOT / "wdl" / "task" / "bin.wdl").read_text()

        self.assertIn('String binner = "lorbin"', workflow)
        self.assertIn("--binner ~{binner}", bin_task)
        self.assertIn('glob("work/output_bins/*.fa")', bin_task)
        self.assertNotIn("SemiBin_*.fa", bin_task)


class DockerStaticTests(unittest.TestCase):
    def test_dockerfile_installs_wdl_report_tools(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text()

        self.assertIn("COPY --from=cycloneseq_report_template", dockerfile)
        self.assertIn("rosa-bio-linux-64.lock", dockerfile)
        self.assertIn("vendor/rosa-${ROSA_VERSION}.wheel.tar.gz", dockerfile)
        self.assertIn("micromamba create -y -n bio", dockerfile)
        self.assertIn("micromamba create -y -n cycloneseq-report", dockerfile)
        self.assertIn("micromamba run -n bio python -m pip install", dockerfile)
        self.assertIn("micromamba run -n cycloneseq-report python -m pip install", dockerfile)
        self.assertIn("/usr/local/bin/rosa", dockerfile)
        self.assertIn("/usr/local/bin/cycloneseq-report", dockerfile)
        self.assertNotIn("ENTRYPOINT", dockerfile)

    def test_required_vendor_archives_are_unignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text()

        self.assertIn("!vendor/lorbin-0.1.0.tar.gz", gitignore)
        self.assertIn("!vendor/rosa-1.1.0.wheel.tar.gz", gitignore)


if __name__ == "__main__":
    unittest.main()
