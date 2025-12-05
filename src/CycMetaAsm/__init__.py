"""CycMetaAsm package.

Provides CLI-accessible building blocks for the metagenome assembly
workflow, including preprocessing, assembly, binning, evaluation, and
summary utilities.
"""

from importlib import metadata

__all__ = ["__version__"]


def __getattr__(name: str):
    if name == "__version__":
        try:
            return metadata.version("CycMetaAsm")
        except metadata.PackageNotFoundError:
            # Fallback for editable installs or source usage.
            return "0.1.0"
    raise AttributeError(name)
