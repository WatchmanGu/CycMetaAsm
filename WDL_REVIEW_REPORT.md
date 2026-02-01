# WDL Workflow Review Report

**Date:** 2026-02-01  
**Repository:** WatchmanGu/CycMetaAsm  
**WDL Version:** 1.0  
**Validation Tool:** MiniWDL 1.13.1  
**Scope:** Complete WDL workflow validation and syntax fixes

---

## Summary

The WDL workflow files in this repository were reviewed for syntax errors, type-checking issues, and workflow logic correctness. One critical syntax error was identified and fixed. All WDL files now pass validation with MiniWDL.

**Root Cause Analysis:**
- The main workflow used invalid optional access syntax (`?.`) which is not supported in WDL 1.0
- This syntax appears to be from a newer WDL spec or was mistakenly introduced

**Impact:**
- The workflow would fail to parse/validate with any WDL engine (Cromwell, MiniWDL)
- This was a blocking issue preventing workflow execution

---

## Fixes Applied

| Issue | File:Line | Change | Rationale |
|-------|-----------|--------|-----------|
| Invalid optional output access syntax | `wdl/workflow.wdl:97` | Changed `classify_step?.classify_result` to `classify_step.classify_result` | In WDL 1.0, outputs from conditional calls (inside `if` blocks) are automatically optional. The `?.` syntax is invalid and unnecessary. The receiving task already declares `classification_tsv` as `File?` (optional), so the type system handles this correctly. |

**Before:**
```wdl
call SM.summarize_results as summary_step {
  input:
    classification_tsv = classify_step?.classify_result,
    ...
}
```

**After:**
```wdl
call SM.summarize_results as summary_step {
  input:
    classification_tsv = classify_step.classify_result,
    ...
}
```

---

## Validation Checklist

✅ **All WDL files pass `miniwdl check` validation:**
- ✅ `wdl/workflow.wdl` - Main workflow validates successfully
- ✅ `wdl/task/preprocess.wdl` - Both tasks (preprocess, RunRosa) validate
- ✅ `wdl/task/assemble.wdl` - assemble_and_select task validates
- ✅ `wdl/task/bin.wdl` - bin_and_checkm2 task validates  
- ✅ `wdl/task/classify.wdl` - classify_bins task validates
- ✅ `wdl/task/summary.wdl` - Both tasks (summarize_results, make_report) validate
- ✅ `wdl/task/evaluate.wdl` - evaluate_assembly task validates

✅ **Type-checking:**
- All input/output types are consistent across task definitions and call sites
- Optional types are properly handled using `File?`, `Array[File]?` declarations
- Conditional outputs are correctly typed as optional automatically by WDL
- `select_first()` is used appropriately to unwrap optionals where needed

✅ **Workflow Logic:**
- Import statements are correct with proper namespace aliases
- All task calls have complete input wiring
- Scatter and conditional logic is sound (classify step only runs if database provided)
- No naming collisions or shadowed variables

✅ **Command Blocks:**
- All declared outputs match command-generated files
- Shell safety flags (`set -euo pipefail`) are used appropriately
- String interpolation syntax (`~{variable}`) is correct throughout

✅ **Runtime Blocks:**
- Docker images are specified for all tasks
- CPU and memory specifications use valid formats
- No invalid runtime keys detected

---

## Remaining Risks / TODOs

### Minor Shellcheck Warning (Not Blocking)

**File:** `wdl/task/evaluate.wdl:29`  
**Warning:** SC2086 - "Double quote to prevent globbing and word splitting"  
**Status:** ⚠️ False Positive - Not a Real Issue

```bash
cycmetaasm evaluate ~{assembly_fasta} work $EVAL_ARGS
                                           ^^^^^^^^^^
```

**Analysis:**  
The unquoted `$EVAL_ARGS` variable is **intentional** and **correct** in this context. The variable contains space-separated command-line arguments that must undergo word splitting to be passed as separate arguments to the `cycmetaasm` command. Quoting it would break this functionality.

**Recommendation:** No action required. This is a common bash pattern for building dynamic argument lists and is safe in this controlled WDL context where user input is sanitized.

**Alternative (if desired):** Could refactor to use bash arrays, but this would be a larger change with no functional benefit:
```bash
# More complex but shellcheck-clean
EVAL_ARGS=()
EVAL_ARGS+=("--assembler" "~{assembler}")
...
cycmetaasm evaluate ~{assembly_fasta} work "${EVAL_ARGS[@]}"
```

---

## Compatibility Notes

✅ **No Breaking Changes**
- Input names remain unchanged
- Output names remain unchanged  
- Task names remain unchanged
- Workflow behavior is preserved exactly

✅ **Backward Compatibility**
- All existing input JSON files should work without modification
- No migration required

---

## Additional Observations

### Code Quality Highlights

1. **Good Optional Handling:** The codebase uses WDL optionals appropriately throughout
   - Conditional CheckM2 database usage
   - Optional classification step
   - Proper use of `select_first()` and `defined()`

2. **Robust Error Handling:** Shell commands use `set -euo pipefail` consistently

3. **Well-Structured:** Clear separation between tasks and workflow, good use of imports

4. **Resource Management:** Runtime blocks specify appropriate CPU/memory for each task

### Type System Usage

The workflow demonstrates proper WDL 1.0 type system usage:
- Optional files: `File?`
- Optional arrays: `Array[File]?`
- Converting optional arrays to concrete: `select_first([scMAGs, []])`
- Automatic optional typing for conditional call outputs

---

## Conclusion

The WDL workflow is now **fully compliant with WDL 1.0 specification** and validates successfully with MiniWDL. The single syntax error that was preventing compilation has been fixed with a minimal, correct change that preserves all workflow semantics.

The workflow should now:
- ✅ Parse successfully with any WDL 1.0 compatible engine
- ✅ Type-check correctly
- ✅ Execute as intended with proper optional handling
- ✅ Maintain backward compatibility with existing configurations

**Quality Bar Met:** ✅ Small, correct fix with no behavior changes
