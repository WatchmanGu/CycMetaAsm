"""Shared helpers used across CycMetaAsm pipelines."""

from __future__ import annotations
import glob
import gzip
import logging

import shutil
import subprocess
from pathlib import Path
from typing import (
    IO,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Union,
)

from Bio import SeqIO

Stream = Optional[Union[int, IO[str], IO[bytes]]]
Command = Sequence[str]
Pipeline = Sequence[Command]

_LOGGER = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """Initialise a basic logging configuration if none exists."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.getLogger().setLevel(level)


def checkpoint(directory: Union[str, Path]) -> bool:
    """Return True if the sentinel file ``_isDone`` exists in ``directory``."""
    return Path(directory, "_isDone").exists()


def mark_done(directory: Union[str, Path]) -> None:
    """Create/overwrite the ``_isDone`` sentinel file inside ``directory``."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    Path(directory, "_isDone").touch()
    _LOGGER.info("Created flag: %s", Path(directory, "_isDone"))


def _ensure_pipeline(commands: Union[Command, Pipeline]) -> Pipeline:
    if not commands:
        raise ValueError("commands must not be empty")
    first = commands[0]
    if isinstance(first, (list, tuple)) and first and isinstance(first[0], str):
        return commands  # type: ignore[return-value]
    if isinstance(commands, (list, tuple)) and all(
        isinstance(token, str) for token in commands
    ):
        return [commands]  # type: ignore[list-item]
    raise TypeError("commands must be a command or list of commands")


def run_cmd(
    commands: Union[Command, Pipeline],
    *,
    check: bool = True,
    log_stdout: bool = False,
    log_stderr: bool = True,
    stdout: Stream = None,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Execute a command or pipeline of commands.

    The implementation favours readability and avoids dynamic command
    generation, which helps Nuitka's static analysis.
    """

    pipeline = _ensure_pipeline(commands)
    processes: List[subprocess.Popen[str]] = []
    previous_process: Optional[subprocess.Popen[str]] = None

    for index, cmd in enumerate(pipeline):
        is_last = index == len(pipeline) - 1
        popen_stdout: Stream
        if is_last:
            popen_stdout = stdout if stdout is not None else subprocess.PIPE
        else:
            popen_stdout = subprocess.PIPE

        _LOGGER.info(
            "Executing command %s/%s: %s", index + 1, len(pipeline), " ".join(cmd)
        )
        proc = subprocess.Popen(
            cmd,
            stdin=previous_process.stdout if previous_process else None,
            stdout=popen_stdout,
            stderr=subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env else None,
        )
        processes.append(proc)
        if previous_process and previous_process.stdout:
            previous_process.stdout.close()
        previous_process = proc

    last_process = processes[-1]
    stdout_data: Optional[Union[str, bytes]]
    stderr_data: Optional[Union[str, bytes]]
    stdout_data, stderr_data = last_process.communicate()
    stdout_text = (
        stdout_data.decode() if isinstance(stdout_data, bytes) else stdout_data
    )
    stderr_text = (
        stderr_data.decode() if isinstance(stderr_data, bytes) else stderr_data
    )
    if log_stdout and stdout_text:
        _LOGGER.info(stdout_text)
    if log_stderr and stderr_text:
        _LOGGER.info(stderr_text)

    for proc in processes[:-1]:
        proc.wait()
    last_return_code = last_process.wait()
    if check and last_return_code != 0:
        raise subprocess.CalledProcessError(last_return_code, pipeline[-1])

    return subprocess.CompletedProcess(
        pipeline[-1], last_return_code, stdout_text, stderr_text
    )


def is_fastq_file(path: Union[str, Path]) -> bool:
    filename = str(path).lower()
    return filename.endswith((".fastq", ".fastq.gz", ".fq", ".fq.gz"))


def is_fasta_file(path: Union[str, Path]) -> bool:
    filename = str(path).lower()
    return filename.endswith((".fasta", ".fasta.gz", ".fa", ".fa.gz"))


def myopen(path: Union[str, Path], mode: str = "rt"):
    """Open plain or gzipped file transparently."""
    path = str(path)
    if path.endswith(".gz"):
        return gzip.open(path, mode)
    return open(path, mode)


def load_fasta_lengths(fasta_path: Union[str, Path]) -> Mapping[str, int]:
    """Return a mapping of contig ids to sequence lengths."""
    lengths: MutableMapping[str, int] = {}
    with myopen(fasta_path, "rt") as handle:
        for record in SeqIO.parse(handle, "fasta"):
            contig_id = record.description.split()[0]
            lengths[contig_id] = len(record.seq)
    return lengths


def collect_fasta_paths(directory: str) -> Iterable[str]:
    patterns = ("*.fasta", "*.fna", "*.fa")
    for pattern in patterns:
        yield from glob.glob(str(Path(directory) / pattern))


def clear_directory(path: Union[str, Path], *, keep_root: bool = True) -> None:
    """Remove directory contents safely."""
    path = Path(path)
    if not path.exists():
        _LOGGER.warning("Directory does not exist: %s", path)
        return

    if keep_root:
        for child in path.iterdir():
            try:
                if child.is_file():
                    child.unlink()
                else:
                    shutil.rmtree(child)
            except Exception as exc:  # pragma: no cover - logging only
                _LOGGER.error("Failed to delete %s: %s", child, exc)
    else:
        shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def read_assembly_info(
    assembly_info: Union[str, Path],
) -> Mapping[str, Mapping[str, str]]:
    """Parse assembly information from flye/metaMDBG output."""
    info: MutableMapping[str, MutableMapping[str, str]] = {}
    with myopen(assembly_info) as handle:
        first_line = handle.readline().strip()
        handle.seek(0)
        if first_line.startswith(">"):
            # ? For metaMDBG assembly info
            for line in handle:
                if not line.startswith(">"):
                    continue
                parts = line[1:].strip().split()
                contig = parts[0]
                entry: MutableMapping[str, str] = {}
                for token in parts[1:]:
                    if "=" in token:
                        key, value = token.split("=", 1)
                        entry[key] = value
                info[contig] = entry
        else:
            for line in handle:
                if line.startswith("#"):
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    contig, _, coverage, circular = parts[:4]
                    info[contig] = {"coverage": coverage, "circular": circular}
    return info


def preset_setting(sequencing_technology: str) -> Mapping[str, str]:
    tech = sequencing_technology.lower()
    if tech == "nanopore":
        return {
            "minimap2": "-ax map-ont --eqx --secondary=no",
            "metaflye": "--nano-raw",
            "metamdbg": "--in-ont",
        }
    if tech == "hifi":
        return {
            "minimap2": "-ax map-hifi --eqx --secondary=no",
            "metaflye": "--nano-raw",
            "metamdbg": "--pacbio-hifi",
        }
    if tech == "cycloneseq":
        return {
            "minimap2": "-a -k 16 -w 13 -A 2 -B 4 -O 4,41 -E 2,1 -s 180 -U70,1000000 --eqx --secondary=no",
            "metaflye": "--nano-raw",
            "metamdbg": "--in-ont",
        }
    return {
        "minimap2": "-ax map-ont --eqx --secondary=no",
        "metaflye": "--nano-raw",
        "metamdbg": "--in-ont",
    }
