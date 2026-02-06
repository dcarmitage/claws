# Task Spec: Add single-judge runner script

## Goal
Create `evals/run_single_judge.sh` — a wrapper that runs just one judge (logic OR consistency) with the same interface as the dual evaluator. This enables re-running only the judge that failed, faster iteration on judge prompt tuning, and standalone debugging.

## Acceptance Criteria

1. **CLI interface:** `./run_single_judge.sh --judge <logic|consistency> --build-id <id> --task-id <id> --spec <path> --taskboard <path> --commit <sha> [--working-dir <path>]`

2. **Logic judge path:** When `--judge logic`, runs only the logic judge with spec, diff, and test output. Prints JSON result and summary line.

3. **Consistency judge path:** When `--judge consistency`, runs only the consistency judge with spec, taskboard, diff, and changed files. Prints JSON result and summary line.

4. **Git artifact gathering:** Reuses the same pattern as `run_dual_judge_eval.sh` — gets diff and changed files from the commit.

5. **Validation:** Output is validated through `validate_output.sh` (same as existing judges).

6. **Exit code:** 0 if judge score >= 8.0, 1 otherwise.

7. **Summary output:** Prints score, tier, and PASS/FAIL to stdout. On FAIL, surfaces failure details (same as dual evaluator).

8. **Error handling:** Rejects invalid `--judge` value with clear error. Validates required files exist.

## Constraints
- Bash only, no new dependencies
- Must live at `evals/run_single_judge.sh`
- Must reuse existing `logic_judge.sh` and `consistency_judge.sh` — no duplication of LLM call logic
- Does NOT log to build_log.py (that's the dual evaluator's job)
