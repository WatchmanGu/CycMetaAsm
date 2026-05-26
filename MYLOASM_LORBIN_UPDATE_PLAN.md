# CycMetaAsm myloasm + LorBin Update Plan

## Goal

Update CycMetaAsm from the current production default of `metaflye + SemiBin2` to the recommended production default of `myloasm + LorBin`, based on the benchmark results in `/data/gukaijie/project/02.metagenomic/workflow/cycmetaasm_bench`.

CycMetaAsm remains a production-style single-sample workflow, not a benchmark workflow. A formal run must select exactly one assembler and one binner.

## User Decisions

1. Copy `vendor/lorbin-0.1.0.tar.gz` directly from the benchmark project into CycMetaAsm.
2. Use a new Docker image tag format such as `cycmetaasm:v1.1.0`; do not overwrite existing tags.
3. Change default behavior to `myloasm + lorbin`.
4. Preserve old behavior through `--assembler metaflye --binner semibin2`.
5. Silently ignore `--preset` when `--assembler myloasm` is used.
6. Do not fix `metamdbg`; remove it from exposed choices and documented user-facing options.

## Files And Directories To Update

### Python Source

- `src/CycMetaAsm/cli.py`
- `src/CycMetaAsm/pipelines/workflow.py`
- `src/CycMetaAsm/pipelines/assembly.py`
- `src/CycMetaAsm/pipelines/binning.py`
- `src/CycMetaAsm/utils.py`

### WDL

- `wdl/workflow.wdl`
- `wdl/task/assemble.wdl`
- `wdl/task/bin.wdl`
- `wdl/task/preprocess.wdl`
- `wdl/task/classify.wdl`
- `wdl/task/summary.wdl`
- `wdl/task/evaluate.wdl`
- `wdl/app_config.json`

### Docker And Environment

- `Dockerfile`
- `environment.yml`
- `conda-linux-64.lock`
- `vendor/lorbin-0.1.0.tar.gz`
- optional LorBin support environment files copied or adapted from benchmark if needed

### Docs And Examples

- `AGENTS.md`
- `README.md`
- `example_inputs_minimal.json`
- `example_inputs_complete.json`
- `tests/test_input.json` if still relevant to current WDL inputs
- new tests under `test/assembler_binner_update/` while preserving existing `tests/`

## Current Key Entries

- CLI entry: `pyproject.toml` defines `cycmetaasm = CycMetaAsm.cli:main`.
- Python package entry: `src/CycMetaAsm/__main__.py` calls `cli.main()`.
- Full Python pipeline entry: `src/CycMetaAsm/pipelines/workflow.py::run_pipeline`.
- Production WDL entry: `wdl/workflow.wdl`.
- Current Docker image copies precompiled `build/CycMetaAsm.bin` to `/usr/local/bin/cycmetaasm`.

## Important Current Mismatches

- `README.md` and CLI expose `metamdbg`, but `AssemblyRunner` only supports `metaflye`.
- Binning has no real binner selector; `--binning-model` is a SemiBin2 environment model, not a binner choice.
- `pipeline --assembler` currently lacks strict choices and can silently fall back through preset handling.
- WDL currently uses multiple Docker images: `cycmetaasm:v1.0.0`, `rosa:0.2.14.0`, and `cycloneseq-report:v1.4.0`.
- `wdl/task/bin.wdl` hard-codes `SemiBin_*.fa` outputs.
- Docker/environment files currently lack `myloasm` and LorBin.
- Docker uses a precompiled binary, so source updates require rebuilding `build/CycMetaAsm.bin` before image build.

## AGENTS.md Plan

Create root `AGENTS.md` with project-specific rules:

- CycMetaAsm is a production single-sample workflow, not a benchmark workflow.
- Formal runs select exactly one assembler and one binner.
- Default recommended combination is `myloasm + lorbin`.
- Historical behavior is preserved through `--assembler metaflye --binner semibin2`.
- Do not silently change output directory structure.
- WDL tasks must use one Docker image tag.
- Python source changes require rebuilding the precompiled binary before production Docker builds.
- Keep `--binning-model` as a SemiBin2 environment parameter only.
- Do not expose `metamdbg` unless it is intentionally reintroduced and fully tested later.

## Python Update Plan

### CLI

- Define assembler choices as `myloasm` and `metaflye`.
- Remove `metamdbg` from exposed CLI choices and docs.
- Define binner choices as `lorbin` and `semibin2`.
- Change default assembler to `myloasm`.
- Add `--binner` to `bin` and `pipeline`, defaulting to `lorbin`.
- Keep `--binning-model` unchanged for SemiBin2 compatibility.
- Clarify help text that `--binning-model` only affects SemiBin2.
- Keep `--preset`, but silently ignore it for `myloasm`.
- Add strict choices for `pipeline --assembler` and related assembler arguments where user-facing.
- Fix the obvious `args.metaquastq` typo to `args.metaquast` if touched in the same file.

### Workflow

- Add `binner: str = "lorbin"` to `PipelineConfig`.
- Pass `binner` into `BinningConfig`.
- Stop silently falling back to `metaflye` presets for unknown assemblers.
- Preserve stable output directories such as `assembly`, `binning`, `summary`.

### Assembly

- Add `myloasm_path: str = "myloasm"` to `AssemblyConfig`.
- Implement `_run_myloasm()` using:

```bash
myloasm <reads.fastq.gz> -o <assembly_dir> -t <threads>
```

- Search known myloasm outputs:
  - `<assembly_dir>/assembly.fasta`
  - `<assembly_dir>/assembly_primary.fa`
- Standardize the selected output to `<assembly_dir>/assembly.fasta`.
- Continue supporting `metaflye` unchanged.
- Remove exposed support for `metamdbg`; no new implementation for it.
- Return `assembly.fasta` as both assembly FASTA and fallback assembly-info source for myloasm.

### Binning

- Add `binner: str = "lorbin"` and `lorbin_path: str = "LorBin"` to `BinningConfig`.
- Keep old `binning_tool` field only if needed for internal/backward compatibility.
- Split binning into `lorbin` and `semibin2` branches.
- Reuse minimap2/samtools alignment output at `<output>/aligned.bam`.
- Run LorBin with:

```bash
LorBin bin --fasta <assembly.fasta> --output <output> --num_process <threads> --bam <aligned.bam>
```

- Standardize LorBin bins into `<output>/output_bins/*.fa`.
- Keep SemiBin2 output in `<output>/output_bins`.
- If `--binner lorbin` and `--binning-model` is provided, ignore `--binning-model` without breaking old JSON/WDL inputs.

### Utilities

- Add a `myloasm` preset entry if needed.
- Remove or stop exposing `metamdbg` in user-facing choices.
- Ensure empty presets do not cause command construction errors.

## Parameter Design

### Assembler

```bash
--assembler {myloasm,metaflye}
```

Default:

```bash
--assembler myloasm
```

Compatibility:

```bash
--assembler metaflye
```

### Binner

```bash
--binner {lorbin,semibin2}
```

Default:

```bash
--binner lorbin
```

Compatibility:

```bash
--assembler metaflye --binner semibin2 --binning-model global
```

## Docker Plan

- Copy benchmark LorBin vendor archive:
  - from `/data/gukaijie/project/02.metagenomic/workflow/cycmetaasm_bench/vendor/lorbin-0.1.0.tar.gz`
  - to `vendor/lorbin-0.1.0.tar.gz`
- Add `myloasm` to `environment.yml` and the conda lockfile workflow.
- Use a separate LorBin conda environment if required by Python/PyTorch constraints.
- Symlink `LorBin` into the production PATH.
- Install or include `rosa` and `cycloneseq-report` in the same production image.
- Standardize WDL runtime Docker image to a new non-overwriting tag such as `cycmetaasm:v1.1.0`.
- Rebuild `build/CycMetaAsm.bin` before building the Docker image.

## WDL Plan

- Change defaults to `assembler = "myloasm"` and `binner = "lorbin"`.
- Add `String binner = "lorbin"` to `wdl/workflow.wdl` and `wdl/task/bin.wdl`.
- Pass `--binner ~{binner}` to `cycmetaasm bin`.
- Keep passing `--binning-model ~{binning_mode}` for SemiBin2 compatibility.
- Change bin output glob from `SemiBin_*.fa` to `*.fa` under `work/output_bins`.
- Use one Docker image tag, for example `cycmetaasm:v1.1.0`, across all WDL tasks including Rosa and report tasks.
- Update `wdl/app_config.json` descriptions and defaults.

## Test Plan

- Add tests under `test/assembler_binner_update/` without deleting existing `tests/`.
- Add mocked CLI/tool tests for:
  - `myloasm` output normalization
  - `metaflye` backward compatibility
  - `LorBin` bin normalization
  - `SemiBin2` backward compatibility
  - absence of exposed `metamdbg`
  - defaults `myloasm + lorbin`
- Add WDL static checks for:
  - all runtime Docker tags are `cycmetaasm:v1.1.0`
  - `binner` input exists
  - bin glob is generalized
- Add optional real-tool smoke tests gated by installed dependencies and databases.

## Execution Order

1. Save this plan.
2. Add `AGENTS.md`.
3. Update Python CLI/config/source.
4. Add mocked tests for Python behavior.
5. Update WDL and WDL tests.
6. Update examples and docs.
7. Copy LorBin vendor archive and update Docker/environment files.
8. Run available Python and static tests.
9. Report remaining Docker/lockfile actions that require environment solving or binary rebuilding.

## Risks And Rollback

- If LorBin installation fails, default can be temporarily changed back to `semibin2` while keeping the new parameter interface.
- If myloasm output names differ, extend output candidate search without changing downstream paths.
- If the single Docker image becomes too large or dependency-conflicted, keep the Python/WDL interface changes but defer production image publication until the dependency conflict is solved.
- If WDL consumers depend on SemiBin-specific file names, the standardized `<output>/output_bins/*.fa` contract should be documented as the supported interface.
- Rollback of default behavior is limited to changing defaults back to `metaflye + semibin2`; old behavior remains available by explicit parameters.
