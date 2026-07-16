# Full Pipeline Docker Test

This directory contains the long-running, database-backed CycMetaAsm Docker
pipeline smoke test. The test uses the repository sample reads and external
database paths available on the production workstation. It runs the Python
pipeline with polish enabled by default, then runs the WDL-equivalent Rosa QC
and `cycloneseq-report` report generation steps.

Run the full test explicitly:

```bash
RUN_CYCMETAASM_FULL_PIPELINE=1 conda run -n meta_asm python test/pipeline_full/test_full_pipeline_docker.py
```

Or call the shell runner directly:

```bash
test/pipeline_full/run_full_pipeline_docker.sh
```

Default output directory:

```text
/tmp/opencode/cycmetaasm_full_pipeline_with_dbs
```

Final report path after a successful run:

```text
/tmp/opencode/cycmetaasm_full_pipeline_with_dbs/report/final/sample_CycMetaAsm_Results/sample_CycMetaAsm_Report.html
```

Useful overrides:

```bash
IMAGE=cycmetaasm:v1.1.0 THREADS=4 OUTPUT_ROOT=/tmp/opencode/cycmetaasm_full_pipeline_with_dbs \
  test/pipeline_full/run_full_pipeline_docker.sh
```

Disable polish for faster debugging:

```bash
POLISH=0 RUN_CYCMETAASM_FULL_PIPELINE=1 conda run -n meta_asm python test/pipeline_full/test_full_pipeline_docker.py
```
