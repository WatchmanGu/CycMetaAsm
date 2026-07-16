# Metagenome assembly workflow for DCS platform

Based on WDL.

`workflow.wdl` is the DCS-compatible standalone workflow. It inlines the task
definitions from `../wdl/task/` and removes all WDL imports because DCS accepts
only one WDL file for the pipeline.

`smoke_inputs.json` is a Cromwell smoke-test input set using the bundled
`../wdl/test/sample.fastq.gz` file. In this environment, bypass the local proxy
when calling the Cromwell REST API, for example:

```bash
curl --noproxy '*' -X POST http://127.0.0.1:18000/api/workflows/v1 \
  -F workflowSource=@dcs/workflow.wdl \
  -F workflowInputs=@dcs/smoke_inputs.json
```
