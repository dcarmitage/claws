# Taskboard: Single judge runner

## Build: LIVE002
## Task: T1 — Add single-judge runner script

### Status: IN PROGRESS

### Scope
- Single new file: `evals/run_single_judge.sh`
- No changes to existing files
- Wraps existing `logic_judge.sh` and `consistency_judge.sh`

### Acceptance
- [ ] Script runs with `--judge logic` and produces valid output
- [ ] Script runs with `--judge consistency` and produces valid output
- [ ] Invalid `--judge` value rejected with error
- [ ] Missing required args rejected with error
- [ ] Exit code reflects pass/fail threshold (8.0)
- [ ] Failure details surfaced on FAIL
