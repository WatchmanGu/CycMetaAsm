"""Module entry point for ``python -m CycMetaAsm``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

if __package__ is None or __package__ == "":  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    package_name = "CycMetaAsm"
else:
    package_name = __package__

try:
    main = importlib.import_module(f"{package_name}.cli").main
except ModuleNotFoundError:  # pragma: no cover - allow execution from source tree
    from .cli import main  # type: ignore[import]


if __name__ == "__main__":
    main()
