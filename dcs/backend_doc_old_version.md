# CycloneFlow后端接口文档

**注意**: 该文档描述的是CycloneFlow后端接口的旧版本，可能不再适用于当前版本。新版使用docker容器化运行，接口地址需要根据新版运行地址实际情况调整。

## 登录接口

### request

```json
{
  "path": "/analysis/login/",
  "method": POST,
  "parameters": {
    "username": "admin",
    "password":"CycloneFlow01admin"
  }
}

```

### response

```json
{
    "csrf_token": "Qpzl0UYNhvl9rmnpfHPo4EqDszNqaHRNiuYhVvYmGAVxQ2TfKlnnpyTK4M2G5WgZ",
    "msg": "success",
    "user": {
        "email": "demo@example.com",
        "id": 4,
        "username": "demo"
    }
}
```

## 登出接口

### request

```json
{
  "path": "/analysis/logout/",
  "method": POST
}

```

### response

```json
{
    "msg": "demo logout success"
}
```

## 注册接口

### request

```json
{
  "path": "/analysis/register/",
  "method": POST,
  "parameters": {
    "username": "test@gmail.com",
    "password":"test1234",
  }
}

```

### response

```json
{
    "csrf_token": "YETaWtBaImO31RbU5nw0xuZ9SsZg0cxK6WgrMwdas1EmB1yuVUfF7gSiZnGSxNRa",
    "message": "User created successfully",
    "user": {
        "username": "test@gmail.com",
        "id": 6
    }
}
```

## 获取任务状态

### request

```json
{
  "path": "/analysis/getTaskOverview/",
  "method": POST,
  "parameters": 
  "X-CSRFToken":******
}

```

### response

```json
{
    "activeTask": 0,
    "doneTask": 1,
    "queuedTask": 0,
    "terminatedTask": 5,
    "totalTask": 6
}
```

## 获取服务器资源

### request

```json
{
  "path": "/analysis/sourceUsage/",
  "method": POST,
  "parameters": 
  "X-CSRFToken":******
}
```

### response

```json
{
    "cpu": 1.7,
    "disk": 71.3,
    "ram": 11.3
}
```

## 添加工具

### request

```json
{
  "path": "/analysis/addTool/",
  "method": POST,
  "parameters": {
    "packagePath":"/path/toolpackage"
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "created": "2025-07-09",
    "id": 9,
    "message": "Tool created successfully",
    "tool_name": "CNV",
    "tool_version": "V1.0.0.0"
}
```

## 获取工具列表

### request

```json
{
  "path": "/analysis/getToolList/",
  "method": POST,
  "parameters": {
    "pageNum": 1,
    "pageSize": 10,
    "toolName": "CNV"
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "pagination": {
        "currentPage": 1,
        "pageSize": "10",
        "total": 1,
        "totalPages": 1
    },
    "tools": [
        {
            "toolDesc": "一个做 CNV 检测的工具",
            "toolDesc_en": "a CNV tool",
            "toolID": 10,
            "toolImg": "/data/cromwell_workdir/CNV_V10.0.0.0/logo.jpg",
            "toolName": "CNV",
            "versions": [
                "V10.0.0.0"
            ]
        }
    ]
}
```

## 删除工具

### request

```json
{
  "path": "/analysis/deleteTool/",
  "method": POST,
  "parameters": {
    "toolID":8
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "code": 0,
    "message": "Tool deleted successfully",
    "toolID": "8"
}
```

## 获取工具详情

### request

```json
{
  "path": "/analysis/getToolDetail/",
  "method": POST,
  "parameters": {
    "toolID":8
    "version":"V1.0.0.0"
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "developer": "tester",
    "inFileDesc": [
        "原始FASTQ文件：测序原始数据（R1/R2双端文件或单端文件）",
        "参考基因组：hg19/hg38等版本FASTA文件（需包含索引）",
        "接头序列文件：Illumina/TruSeq等平台适配器序列（用于cutadapt）",
        "目标区域文件（WES必需）：捕获目标区域的BED文件（如全外显子组）",
        "对照样本BAM文件（配对分析）：正常样本的预处理BAM（肿瘤-正常配对）",
        "注释数据库：ANNOVAR/VEP所需的人类基因组数据库文件",
        "质控阈值：比对率、覆盖深度等自定义阈值（如>90%，≥30X）",
        "GC校正文件（可选）：参考基因组GC内容曲线文件",
        "验证引物设计参考：目标CNV区域坐标（用于下游qPCR验证）",
        "流程配置文件：YAML/JSON格式的运行参数配置文件"
    ],
    "inFileDesc_en": [
        "Raw FASTQ files: Sequencing raw data (paired-end R1/R2 files or single-end files)",
        "Reference genome: FASTA files for versions like hg19/hg38 (must include index files)",
        "Adapter sequence file: Platform-specific adapters (e.g., Illumina/TruSeq) for cutadapt",
        "Target regions file (Required for WES): BED file defining capture regions (e.g., whole exome)",
        "Control sample BAM file (For paired analysis): Preprocessed BAM of normal sample (tumor-normal pairing)",
        "Annotation databases: Human genome database files required for ANNOVAR/VEP",
        "QC thresholds: Custom thresholds (e.g., alignment rate >90%, coverage depth ≥30X)",
        "GC correction file (Optional): Reference genome GC content profile",
        "Verification primer design reference: Target CNV region coordinates (for downstream qPCR validation)",
        "Workflow configuration file: Run parameter file in YAML/JSON format"
    ],
    "outFileDesc": [
        "QC报告：FastQC输出的HTML质量报告（含测序质量/接头污染/GC分布）",
        "预处理日志：Trimmomatic/cutadapt的trimming统计报告（保留reads比例）",
        "比对BAM文件：排序去重后的BAM文件（含samtools index生成的.bai索引）",
        "CNV原始结果：分段拷贝数表（Control-FREEC的ratio.txt / CNVkit的.cns）",
        "过滤后CNV结果：经过置信度过滤的BED/VCF文件（含断点坐标/拷贝数状态）",
        "注释结果表：CSV/TXT格式的注释报告（基因/临床意义/频率数据库关联）",
        "可视化图谱：PDF格式的全基因组CNV圈图（Circos或染色体分布图）",
        "IGV截图：重点CNV区域的局部可视化截图（PNG/PDF格式）",
        "汇总报告：MultiQC生成的整合质控HTML报告（含各阶段QC指标）",
        "验证引物列表：待验证CNV的qPCR引物序列信息（FASTA格式）",
        "下游结果包（可选）：cBioPortal输入文件/驱动基因整合报告"
    ],
    "outFileDesc_en": [
        "QC Report: HTML quality report from FastQC (including sequencing quality/adapter contamination/GC distribution)",
        "Preprocessing Log: Trimming statistics from Trimmomatic/cutadapt (retained reads percentage)",
        "Aligned BAM Files: Sorted and deduplicated BAM files (with .bai index generated by samtools index)",
        "Raw CNV Results: Segmented copy number tables (Control-FREEC's ratio.txt / CNVkit's .cns files)",
        "Filtered CNV Results: Confidence-filtered BED/VCF files (with breakpoint coordinates/copy number states)",
        "Annotation Report: CSV/TXT formatted annotation report (gene/clinical significance/frequency database associations)",
        "Visualization Plots: PDF format genome-wide CNV circos plots (Circos or chromosome distribution maps)",
        "IGV Screenshots: Local visualization screenshots of key CNV regions (PNG/PDF format)",
        "Summary Report: Consolidated QC HTML report generated by MultiQC (including multi-stage QC metrics)",
        "Verification Primer List: qPCR primer sequences for target CNVs (FASTA format)",
        "Downstream Package (Optional): cBioPortal input files/driver gene integration report"
    ],
    "published": "2023-12-31",
    "toolDesc": "一个做 CNV 检测的工具",
    "toolDesc_en": "a CNV tool",
    "toolID": 10,
    "toolName": "CNV",
    "version": "V10.0.0.0",
    "workflowDesc": [
        "原始数据质控：FastQC（评估FASTQ质量、GC含量、长度分布、接头污染）",
        "数据预处理：Trimmomatic/cutadapt（切除Q<20低质量碱基，去除接头）",
        "序列比对：BWA-MEM/STAR（比对到hg38参考基因组，输出BAM）",
        "BAM文件处理：samtools/Picard（排序+去重），samtools index（索引生成）",
        "CNV检测：可选工具[Control-FREEC(全基因组RD比值)/CNVkit(全外显子标准化)/GATK gCNV(概率模型)]，关键参数(窗口大小/GC校正/肿瘤-正常配对)",
        "结果过滤与注释：过滤(长度<1kb或高频CNV)，注释(ANNOVAR/VEP关联基因功能)",
        "可视化与报告：IGV(局部可视化)/R-ggplot2(全基因组图谱)，输出(BED文件/统计表/PDF报告)",
        "质量控制：MultiQC监控(比对率>90%/覆盖深度≥30X/批次效应)",
        "下游分析(可选)：SNV-Indel整合/TCGA预后关联(cBioPortal)/qPCR实验验证"
    ],
    "workflowDesc_en": [
        "Raw Data QC: FastQC (assess FASTQ quality, GC content, length distribution, adapter contamination)",
        "Data Preprocessing: Trimmomatic/cutadapt (trim Q<20 low-quality bases, remove adapters)",
        "Sequence Alignment: BWA-MEM/STAR (align to hg38 reference genome, output BAM)",
        "BAM Processing: samtools/Picard (sort + deduplicate), samtools index (generate index)",
        "CNV Detection: Optional tools [Control-FREEC (WGS RD ratio)/CNVkit (WES normalization)/GATK gCNV (probabilistic model)], key parameters (window size/GC correction/tumor-normal pairing)",
        "Result Filtering & Annotation: Filter (length<1kb or high-frequency CNVs), Annotation (ANNOVAR/VEP for gene function association)",
        "Visualization & Reporting: IGV (local visualization)/R-ggplot2 (genome-wide map), Output (BED files/statistical tables/PDF reports)",
        "Quality Control: MultiQC monitoring (alignment rate>90%/coverage depth≥30X/batch effects)",
        "Downstream Analysis (Optional): SNV-Indel integration/TCGA prognosis association (cBioPortal)/qPCR experimental validation"
    ]
}
```

## 获取工具参数列表

### request

```json
{
  "path": "/analysis/getToolparameter/",
  "method": POST,
  "parameters": {
    "toolID":6,
    "version":"V2.0.0.0"
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "params": [
        {
            "controlType": "bool",
            "default": true,
            "desc": "一个布尔值",
            "desc_en": "a bool value",
            "key": "CNV.bool",
            "name": "测序布尔值测试",
            "name_en": "test bool value",
            "required": true,
            "type": "Boolean",
            "visible": true
        },
        {
            "controlType": "file",
            "default": true,
            "desc": "测试文件接口",
            "desc_en": "test file api",
            "key": "CNV.file",
            "name": "测序文件测试",
            "name_en": "test file",
            "required": true,
            "type": "Boolean",
            "visible": true
        },
        {
            "controlType": "file",
            "default": true,
            "desc": "测试字符串",
            "desc_en": "test string",
            "key": "CNV.string",
            "name": "测序字符串测试",
            "name_en": "test string",
            "required": true,
            "type": "Boolean",
            "visible": true
        }
    ],
    "toolID": 10
}
```

## 投递任务

### request

```json
{
  "path": "/analysis/taskPost/",
  "method": POST,
  "parameters": {
    "toolID":"6",
    "version": "V2.0.0.0",
    list=[{
        "taskName": "test",
        "params": {
            "CNV.sample_type": "test",
            "CNV.sample_name": "test",
            "CNV.input_fq_file": "/data/lihanyu/test_data/2407C05791011/2407C05791011_barcode1/2407C05791011_barcode1_01.fastq.gz",
            "CNV.qc_script": "./qc/q_value.py",
            "CNV.CN_script": "./CN_value/CN_calculate.py",
            "CNV.template_file": "./result_report/templates/report_template.html",
            "CNV.report_script":"./result_report/report.py",
            "CNV.bed_file":"./bed_file/GC_100kb_2_filter.bed",
            "CNV.GRch38_ref_file":"./ref/GRCh38_Y_mask.fa"
            }
        }
  ]
  }
  "X-CSRFToken":******
}
```

### response

```json
[{"taskID": 5, "taskName": "test", "taskStatus": "Submitted"}]
error
{"message": "system busy"}
```

## 获取任务列表

### request

```json
{
  "path": "/analysis/getTaskList/",
  "method": POST,
  "parameters": {
    "pageNum": 1,
    "pageSize": 10,
    "startTime": "2023-08-15T14:30:00",
    "endTime":"2023-08-15T14:30:00",
    "taskStatus": "COMPLETE",
    "toolName":"CNV"
    "toolVersion":"V1.1.0.0"
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "pagination": {
        "currentPage": 1,
        "pageSize": 10,
        "total": 2,
        "totalPages": 1
    },
    "tasks": [
        {
            "taskID": 4,
            "taskName": "test2",
            "taskRunTime": "00:01:17",
            "taskSendTime": "2025-07-11 15:53:56",
            "taskStatus": "EXECUTOR_ERROR",
            "taskToolName": "CNV",
            "taskToolVersion": "V2.0.0.0"
        },
        {
            "taskID": 5,
            "taskName": "test",
            "taskRunTime": "00:13:18",
            "taskSendTime": "2025-07-11 16:00:59",
            "taskStatus": "COMPLETE",
            "taskToolName": "CNV",
            "taskToolVersion": "V2.0.0.0"
        }
    ]
}
```

## 获取任务详情

### request

```json
{
  "path": "/analysis/getTaskDetail/",
  "method": POST,
  "parameters": {
    "taskID":9
  }
  "X-CSRFToken":******
}
```

### response

```json
{
    "taskEndTime": "2025-07-16 10:24:03",
    "taskErrorLog": null,
    "taskName": "test",
    "taskParams": [
        {
            "desc": "test1234",
            "key": "CNV.input_fq_file",
            "name": "测序文件",
            "required": true,
            "type": "File",
            "value": "/data/lihanyu/test_data/2407C05791011/2407C05791011_barcode1/2407C05791011_barcode1_01.fastq.gz",
            "visible": true
        },
        {
            "desc": "test12345",
            "key": "CNV.sample_name",
            "name": "样本名",
            "required": true,
            "type": "String",
            "value": "test",
            "visible": true
        },
        {
            "desc": "test123456",
            "key": "CNV.sample_type",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "test",
            "visible": true
        },
        {
            "default": "./qc/q_value.py",
            "desc": "test123456",
            "key": "CNV.qc_script",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "./qc/q_value.py",
            "visible": false
        },
        {
            "default": "./CN_value/CN_calculate.py",
            "desc": "test123456",
            "key": "CNV.CN_script",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "./CN_value/CN_calculate.py",
            "visible": false
        },
        {
            "default": "./result_report/templates/report_template.html",
            "desc": "test123456",
            "key": "CNV.template_file",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "./result_report/templates/report_template.html",
            "visible": false
        },
        {
            "default": "./result_report/report.py",
            "desc": "test123456",
            "key": "CNV.report_script",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "./result_report/report.py",
            "visible": false
        },
        {
            "default": "./bed_file/GC_100kb_2_filter.bed",
            "desc": "test123456",
            "key": "CNV.bed_file",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "./bed_file/GC_100kb_2_filter.bed",
            "visible": false
        },
        {
            "default": "./ref/GRCh38_Y_mask.fa",
            "desc": "test123456",
            "key": "CNV.GRch38_ref_file",
            "name": "样本类型",
            "required": true,
            "type": "String",
            "value": "./ref/GRCh38_Y_mask.fa",
            "visible": false
        }
    ],
    "taskPath": {},
    "taskRunTime": "00:00:23",
    "taskSendTime": "2025-07-16 10:23:40",
    "taskStatus": "RUNNING",
    "taskStep": [
        {
            "StepEndTime": "2025-07-16 10:24:03",
            "StepExitCode": null,
            "StepName": "CNV.mapping",
            "StepRunTime": "00:00:06",
            "StepStartTime": "2025-07-16 10:23:56",
            "StepStderr": null,
            "StepStdout": null
        },
        {
            "StepEndTime": "2025-07-16 10:24:03",
            "StepExitCode": null,
            "StepName": "CNV.qc",
            "StepRunTime": "00:00:06",
            "StepStartTime": "2025-07-16 10:23:56",
            "StepStderr": null,
            "StepStdout": null
        }
    ],
    "taskToolName": "CNV",
    "taskToolVersion": "V3.0.0.0"
}
```

## 终止指定任务（可通过列表批量）

### request

```json
{
  "path": "/analysis/cancelTask/",
  "method": POST,
  "parameters": {
    "taskIds":["9", "10"]
  }
  "X-CSRFToken":******
}
```

### response

```json
[
    {
        "code": 200,
        "message": "Abort request accepted",
        "status": "abort_initiated",
        "taskID": "9"
    },
    {
        "code": 200,
        "message": "Abort request accepted",
        "status": "abort_initiated",
        "taskID": "10"
    }
]
```

## 删除指定任务（可通过列表批量）

### request

```json
{
  "path": "/analysis/deleteTask/",
  "method": POST,
  "parameters": {
    "taskIds":["9", "10"]
  }
  "X-CSRFToken":******
}
```

### response

```json
[
    {
        "code": 200,
        "message": "Task deleted successfully",
        "toolID": "9"
    },
    {
        "code": 200,
        "message": "Task deleted successfully",
        "toolID": "10"
    },
    {
        "code": 200,
        "message": "Task not completed, Task deletion failed",
        "toolID": "9"
    },
    {
        "code": 200,
        "message": "Task not completed, Task deletion failed",
        "toolID": "10"
    }
]
```

## 获取路径接口

### request

```json
{
  "path": "/analysis/getPathStructure/",
  "method": POST,
  "parameters": {
    "path":"/data"
  }
  "X-CSRFToken":******
}
```

### response

```python
{
    "entries": [
        {
            "modified": 1702975264.7722197,
            "modified_human": "2023-12-19 16:41:04",
            "name": "path",
            "path": "/data/path",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1703159917.0045855,
            "modified_human": "2023-12-21 19:58:37",
            "name": ".Trash-1000",
            "path": "/data/.Trash-1000",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1704248102.8681793,
            "modified_human": "2024-01-03 10:15:02",
            "name": "SHORT1MIN0",
            "path": "/data/SHORT1MIN0",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1704252673.5961883,
            "modified_human": "2024-01-03 11:31:13",
            "name": "MS_Data",
            "path": "/data/MS_Data",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781417.3840373,
            "modified_human": "2024-06-19 15:16:57",
            "name": "TB2000830F-202404091546470",
            "path": "/data/TB2000830F-202404091546470",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781436.8520374,
            "modified_human": "2024-06-19 15:17:16",
            "name": "TB20010C0E-202405301544170",
            "path": "/data/TB20010C0E-202405301544170",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781447.2520378,
            "modified_human": "2024-06-19 15:17:27",
            "name": "TB200106D6-202405151341400",
            "path": "/data/TB200106D6-202405151341400",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781456.2160378,
            "modified_human": "2024-06-19 15:17:36",
            "name": "TB20010CB0-202405281652531",
            "path": "/data/TB20010CB0-202405281652531",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781466.8400378,
            "modified_human": "2024-06-19 15:17:46",
            "name": "TB20010E3D-202406071029220",
            "path": "/data/TB20010E3D-202406071029220",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781485.0160382,
            "modified_human": "2024-06-19 15:18:05",
            "name": "TB2000D662-202404171741591",
            "path": "/data/TB2000D662-202404171741591",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781491.044038,
            "modified_human": "2024-06-19 15:18:11",
            "name": "TB2000D56C-202404171721190",
            "path": "/data/TB2000D56C-202404171721190",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781514.1160383,
            "modified_human": "2024-06-19 15:18:34",
            "name": "TB2000FF73-202404270744140",
            "path": "/data/TB2000FF73-202404270744140",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1718781524.1600385,
            "modified_human": "2024-06-19 15:18:44",
            "name": "TB200125B9-202406071029271",
            "path": "/data/TB200125B9-202406071029271",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1720161405.142011,
            "modified_human": "2024-07-05 14:36:45",
            "name": "raw_upload.log",
            "path": "/data/raw_upload.log",
            "size": 0,
            "type": "file"
        },
        {
            "modified": 1721614433.8158433,
            "modified_human": "2024-07-22 10:13:53",
            "name": "TB2000AE8B-202407221013531",
            "path": "/data/TB2000AE8B-202407221013531",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721614990.1198456,
            "modified_human": "2024-07-22 10:23:10",
            "name": "TB2000AE8B-202407221023090",
            "path": "/data/TB2000AE8B-202407221023090",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721615087.711846,
            "modified_human": "2024-07-22 10:24:47",
            "name": "TB2000AE8B-202407221024471",
            "path": "/data/TB2000AE8B-202407221024471",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721615651.8158484,
            "modified_human": "2024-07-22 10:34:11",
            "name": "TB2000AE8B-202407221034111",
            "path": "/data/TB2000AE8B-202407221034111",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721615679.6238484,
            "modified_human": "2024-07-22 10:34:39",
            "name": "TB2000AE8B-202407221034390",
            "path": "/data/TB2000AE8B-202407221034390",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721615780.6878488,
            "modified_human": "2024-07-22 10:36:20",
            "name": "TB20014EC0-202407221036201",
            "path": "/data/TB20014EC0-202407221036201",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721615914.7278495,
            "modified_human": "2024-07-22 10:38:34",
            "name": "TB2000AE8B-202407221038341",
            "path": "/data/TB2000AE8B-202407221038341",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721615987.6758497,
            "modified_human": "2024-07-22 10:39:47",
            "name": "TB2000AE8B-202407221039471",
            "path": "/data/TB2000AE8B-202407221039471",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721616220.3238506,
            "modified_human": "2024-07-22 10:43:40",
            "name": "TB2000AE8B-202407221043401",
            "path": "/data/TB2000AE8B-202407221043401",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721617519.059856,
            "modified_human": "2024-07-22 11:05:19",
            "name": "TB2000AE8B-202407221105181",
            "path": "/data/TB2000AE8B-202407221105181",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721618219.2078586,
            "modified_human": "2024-07-22 11:16:59",
            "name": "TB2000AE8B-202407221116591",
            "path": "/data/TB2000AE8B-202407221116591",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721618371.5238593,
            "modified_human": "2024-07-22 11:19:31",
            "name": "TB2000AE8B-202407221119311",
            "path": "/data/TB2000AE8B-202407221119311",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1721810044.5006287,
            "modified_human": "2024-07-24 16:34:04",
            "name": "TB200177D5-202407241634040",
            "path": "/data/TB200177D5-202407241634040",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1722926019.5971084,
            "modified_human": "2024-08-06 14:33:39",
            "name": "TB200190EC-202408061433390",
            "path": "/data/TB200190EC-202408061433390",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1723013162.1494582,
            "modified_human": "2024-08-07 14:46:02",
            "name": "TB200190A1-202408071446020",
            "path": "/data/TB200190A1-202408071446020",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1725856138.5068285,
            "modified_human": "2024-09-09 12:28:58",
            "name": "TB200143E3-202407281227470",
            "path": "/data/TB200143E3-202407281227470",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1736932150.3546426,
            "modified_human": "2025-01-15 17:09:10",
            "name": "TB200150CA-202407311454120",
            "path": "/data/TB200150CA-202407311454120",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1736933436.0020692,
            "modified_human": "2025-01-15 17:30:36",
            "name": ".Trash-1001",
            "path": "/data/.Trash-1001",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1742191340.4544458,
            "modified_human": "2025-03-17 14:02:20",
            "name": "analysis_web",
            "path": "/data/analysis_web",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1747377557.1143734,
            "modified_human": "2025-05-16 14:39:17",
            "name": "cromwell_workdir",
            "path": "/data/cromwell_workdir",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1747380072.0223773,
            "modified_human": "2025-05-16 15:21:12",
            "name": "cromwell_result",
            "path": "/data/cromwell_result",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1747796339.1948054,
            "modified_human": "2025-05-21 10:58:59",
            "name": "tmp_ccf",
            "path": "/data/tmp_ccf",
            "size": 28672,
            "type": "directory"
        },
        {
            "modified": 1747797920.0807745,
            "modified_human": "2025-05-21 11:25:20",
            "name": "h5",
            "path": "/data/h5",
            "size": 12288,
            "type": "directory"
        },
        {
            "modified": 1750383030.0766017,
            "modified_human": "2025-06-20 09:30:30",
            "name": "output_data",
            "path": "/data/output_data",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1753076410.9412537,
            "modified_human": "2025-07-21 13:40:10",
            "name": "analysis_dev",
            "path": "/data/analysis_dev",
            "size": 4096,
            "type": "directory"
        },
        {
            "modified": 1753076631.9014993,
            "modified_human": "2025-07-21 13:43:51",
            "name": "caddy",
            "path": "/data/caddy",
            "size": 4096,
            "type": "directory"
        }
    ],
    "path": "/data"
}
```

## 获取测序信息

### request

```json
{
  "path": "/analysis/getChipInfo/",
  "method": POST,
  "parameters": {
    "pageNum": 1,
    "pageSize": 10,
  }
  "X-CSRFToken":******
}
```

### response

```python
{
    "page": 1,
    "per_page": 10,
    "results": [
        {
            "Average": 2.080395861646536,
            "ChipID": "240711008068",
            "EndTime": "2025-06-17T16:04:57",
            "FlowCellID": "2507402715",
            "LibraryID": "hg002-ys-ys",
            "N50": 7.434,
            "OperUser": "",
            "ProjectID": "hg002-ys-ys",
            "QScore": 12.569300813916882,
            "QcAfter": -1,
            "QcBefore": -1,
            "RID": 83,
            "ReadsCount": 52.24,
            "ReportPath": "/data/output_data/2507402715022/2507402715022.summaryReport.html",
            "RunID": "2507402715022",
            "RunState": 1,
            "RunTime": 573,
            "SlotID": 1,
            "StartTime": "2025-06-17T15:51:40",
            "Through": 0.108686121
        },
        {
            "Average": 1.593508380696497,
            "ChipID": "240711005771",
            "EndTime": "2025-06-17T16:04:53",
            "FlowCellID": "2507402530",
            "LibraryID": "hg002-tiangen-tiangen",
            "N50": 5.914,
            "OperUser": "",
            "ProjectID": "hg002-tiangen-tiangen",
            "QScore": 12.761160820979914,
            "QcAfter": -1,
            "QcBefore": -1,
            "RID": 82,
            "ReadsCount": 48.38,
            "ReportPath": "/data/output_data/2507402530012/2507402530012.summaryReport.html",
            "RunID": "2507402530012",
            "RunState": 1,
            "RunTime": 600,
            "SlotID": 0,
            "StartTime": "2025-06-17T15:51:11",
            "Through": 0.077101903
        },
        {
            "Average": 0.7425362650252109,
            "ChipID": "240711002825",
            "EndTime": "2025-06-13T17:24:30",
            "FlowCellID": "2507404139",
            "LibraryID": "yangben2",
            "N50": 1.268,
            "OperUser": "huyuanyuan",
            "ProjectID": "hongjiyinzu",
            "QScore": 11.130630053447131,
            "QcAfter": -1,
            "QcBefore": 2558,
            "RID": 81,
            "ReadsCount": 15792.79,
            "ReportPath": "/data/output_data/2507404139021/2507404139021.summaryReport.html",
            "RunID": "2507404139021",
            "RunState": 1,
            "RunTime": 84747,
            "SlotID": 1,
            "StartTime": "2025-06-12T16:46:56",
            "Through": 11.726720786
        },
        {
            "Average": 0.9403410506850173,
            "ChipID": "240711001253",
            "EndTime": "2025-06-13T17:24:25",
            "FlowCellID": "2507500206",
            "LibraryID": "yangben1",
            "N50": 3.969,
            "OperUser": "huyuanyuan",
            "ProjectID": "hongjiyinzu",
            "QScore": 11.946807336169918,
            "QcAfter": -1,
            "QcBefore": 2658,
            "RID": 80,
            "ReadsCount": 11136.51,
            "ReportPath": "/data/output_data/2507500206011/2507500206011.summaryReport.html",
            "RunID": "2507500206011",
            "RunState": 1,
            "RunTime": 84787,
            "SlotID": 0,
            "StartTime": "2025-06-12T16:46:00",
            "Through": 10.472113753
        },
        {
            "Average": 5.898307464626612,
            "ChipID": "240711004108",
            "EndTime": "2025-06-12T15:15:08",
            "FlowCellID": "2507404920",
            "LibraryID": "2025060602",
            "N50": 14.516,
            "OperUser": "",
            "ProjectID": "840-B-0612",
            "QScore": 11.095492074520891,
            "QcAfter": -1,
            "QcBefore": 1265,
            "RID": 79,
            "ReadsCount": 255.42,
            "ReportPath": "/data/output_data/2507404920024/2507404920024.summaryReport.html",
            "RunID": "2507404920024",
            "RunState": 1,
            "RunTime": 13132,
            "SlotID": 1,
            "StartTime": "2025-06-12T11:08:43",
            "Through": 1.506533896
        },
        {
            "Average": 5.89129044143531,
            "ChipID": "240711002943",
            "EndTime": "2025-06-12T14:36:16",
            "FlowCellID": "2507405064",
            "LibraryID": "2025060602",
            "N50": 14.409,
            "OperUser": "",
            "ProjectID": "880-A-0612",
            "QScore": 11.219147812073007,
            "QcAfter": -1,
            "QcBefore": 1551,
            "RID": 78,
            "ReadsCount": 255.67,
            "ReportPath": "/data/output_data/2507405064014/2507405064014.summaryReport.html",
            "RunID": "2507405064014",
            "RunState": 1,
            "RunTime": 10818,
            "SlotID": 0,
            "StartTime": "2025-06-12T11:08:23",
            "Through": 1.506202662
        },
        {
            "Average": 1.2841717139599884,
            "ChipID": "240711007560",
            "EndTime": "2025-06-06T09:46:40",
            "FlowCellID": "2507402965",
            "LibraryID": "D11-WGA-1ng",
            "N50": 1.847,
            "OperUser": "ys",
            "ProjectID": "D11-WGA-1ng",
            "QScore": 11.884653078850565,
            "QcAfter": 2658,
            "QcBefore": 2764,
            "RID": 77,
            "ReadsCount": 9567.21,
            "ReportPath": "/data/output_data/2507402965021/2507402965021.summaryReport.html",
            "RunID": "2507402965021",
            "RunState": 1,
            "RunTime": 79985,
            "SlotID": 1,
            "StartTime": "2025-06-05T10:35:24",
            "Through": 12.285936611
        },
        {
            "Average": 1.5235649065423535,
            "ChipID": "240711500169",
            "EndTime": "2025-06-04T15:18:05",
            "FlowCellID": "2507401444",
            "LibraryID": "jiehefenzhiganjun",
            "N50": 2.84,
            "OperUser": "huyuanyuan",
            "ProjectID": "danjun",
            "QScore": 9.527562573810037,
            "QcAfter": 2201,
            "QcBefore": 2194,
            "RID": 76,
            "ReadsCount": 3606.39,
            "ReportPath": "/data/output_data/2507401444011/2507401444011.summaryReport.html",
            "RunID": "2507401444011",
            "RunState": 1,
            "RunTime": 86407,
            "SlotID": 0,
            "StartTime": "2025-06-03T14:12:53",
            "Through": 5.494573814
        },
        {
            "Average": 5.190461524425302,
            "ChipID": "240711504214",
            "EndTime": "2025-05-29T19:18:39",
            "FlowCellID": "2507403231",
            "LibraryID": "zhongkejiyin",
            "N50": 18.816,
            "OperUser": "huyuanyuan",
            "ProjectID": "DANJUN",
            "QScore": 11.683660464281127,
            "QcAfter": 2415,
            "QcBefore": 2426,
            "RID": 75,
            "ReadsCount": 290.46,
            "ReportPath": "/data/output_data/2507403231011/2507403231011.summaryReport.html",
            "RunID": "2507403231011",
            "RunState": 1,
            "RunTime": 9648,
            "SlotID": 0,
            "StartTime": "2025-05-29T16:12:12",
            "Through": 1.507605883
        },
        {
            "Average": 1.6252771911817536,
            "ChipID": "240711001454",
            "EndTime": "2025-05-21T16:08:55",
            "FlowCellID": "2507403317",
            "LibraryID": "HIV-4500b-Q",
            "N50": 4.253,
            "OperUser": "",
            "ProjectID": "HIV-4500b-Q",
            "QScore": 11.259349590509585,
            "QcAfter": 2547,
            "QcBefore": 2578,
            "RID": 74,
            "ReadsCount": 1363.99,
            "ReportPath": "/data/output_data/2507403317021/2507403317021.summaryReport.html",
            "RunID": "2507403317021",
            "RunState": 1,
            "RunTime": 15204,
            "SlotID": 1,
            "StartTime": "2025-05-21T11:26:07",
            "Through": 2.216861836
        }
    ],
    "total_pages": 9,
    "total_records": 83
}
```

## 分析结果汇总

### request

```json
{
  "path": "/analysis/summaryTask/",
  "method": POST,
  "parameters": {
    "taskIdList": ["1", "2","3","4","5","6","7","8","9","10"]
  }
  "X-CSRFToken":******
}
```

### response

```python
Content-Disposition: attachment; filename="task_summary.txt"

sample_name,reads_number,base_number,GC_number,q7_value,mean_length,chr13,chr13_Qual,chr18,chr18_Qual,chr21,chr21_Qual,DGS,DGS_Qual
2507504679021_barcode7,1808267,1048449311,44.44%,98.75%,579.81,1.982,Negative,2.014,Negative,2.024,Negative,1.896,Negative
2507504679021_barcode6,1793178,1030490020,44.37%,98.80%,574.67,2.006,Negative,2.008,Negative,1.992,Negative,1.872,Negative
2507504679021_barcode8,1919750,1071480615,44.29%,97.83%,558.14,1.992,Negative,1.998,Negative,1.976,Negative,1.978,Negative
2507504679021_barcode9,1925748,1102834452,44.10%,95.33%,572.68,1.972,Negative,1.992,Negative,2.77,Positive,1.89,Negative
2507504679021_barcode10,1555493,995045883,44.34%,98.04%,639.7,1.972,Negative,2.002,Negative,2.75,Positive,1.706,Negative
2507504679021_barcode11,2270424,1309350041,44.08%,95.09%,576.7,1.958,Negative,2.864,Positive,2.004,Negative,1.86,Negative
2507504679021_barcode12,1878043,1093019294,44.12%,96.66%,582.0,1.972,Negative,2.006,Negative,2.748,Positive,1.88,Negative
2507504679021_barcode13,1720730,1022119823,44.32%,98.07%,594.0,1.992,Negative,2.006,Negative,2.038,Negative,1.166,Positive
2507504679021_barcode14,1962040,1062281207,44.46%,96.48%,541.42,1.976,Negative,2.002,Negative,2.754,Positive,1.952,Negative
2507504679021_barcode15,1696142,1017139128,44.57%,98.44%,599.68,1.974,Negative,2.018,Negative,2.718,Positive,1.848,Negative
```

## 批量分析结果下载

### request

```json
{
  "path": "/analysis/batchDownload/",
  "method": POST,
  "parameters": {
    "taskIds":["1", "2"]
  }
  "X-CSRFToken":******
}
```

### response 返回文件

```json
HTTP/1.1 200 OK
Content-Disposition: attachment; filename="download.zip"
Content-Language: zh-hans
Content-Length: 18054
Content-Type: application/zip
Cross-Origin-Opener-Policy: same-origin
Date: Tue, 09 Dec 2025 07:02:53 GMT
Referrer-Policy: same-origin
Server: Caddy
Server: gunicorn
Vary: origin, Accept-Language, Cookie
X-Content-Type-Options: nosniff
X-Frame-Options: DENY

Downloading 17.63 kB to "download.zip"
Done. 17.63 kB in 0.00057s (30.27 MB/s)
```

## 限制大小分析结果下载

### request

```json
{
  "path": "/analysis/checkDownload/",
  "method": GET,
  "parameters": {
    "path":"/test/data"
  }
  "X-CSRFToken":******
}
```

### response（文件大小超过 5GB）

```json
{
    "error": "File is too large",
    "limit_bytes": 5368709120,
    "size_bytes": 14228584117
}
```

### response（文件大小未超过 5GB）

重定向到下载路径由 caddy 进行文件传输