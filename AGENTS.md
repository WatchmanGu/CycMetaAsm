# CycMetaAsm Project Guidance

- CycMetaAsm is a production single-sample workflow, not a benchmark workflow.
- A formal production run must select exactly one assembler and exactly one binner.
- The recommended default is `myloasm + lorbin`.
- The historical production behavior remains available with `--assembler metaflye --binner semibin2`.
- Do not silently change the stable output directory structure (`assembly`, `subset_contigs`, `binning`, `classify`, `summary`).
- Keep `--binning-model` as a SemiBin2 environment-model parameter only; LorBin ignores it.
- Do not expose `metamdbg` unless it is intentionally reintroduced with a tested implementation.
- All WDL tasks should use the same production Docker tag, currently `cycmetaasm:v1.1.0`.
- Python source changes require rebuilding `build/CycMetaAsm.bin` before publishing a production Docker image.
- Preserve existing `tests/` content; add new focused regression checks under `test/` when needed.
