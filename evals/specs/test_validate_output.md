# Task Spec: Add tests for validate_output.sh

## Goal
Create a test script `evals/tests/test_validate_output.sh` that exercises `validate_output.sh` with valid and invalid judge JSON inputs, ensuring the validator correctly gates the pipeline.

## Acceptance Criteria

1. **Valid input accepted:** A well-formed judge output JSON with all required fields (judge, score, tier, timestamp) and valid values must exit 0 and print "VALID".

2. **Missing field rejected:** JSON missing any required field (judge, score, tier, timestamp) must exit 1 and print an error mentioning the missing field.

3. **Score out of range rejected:** JSON with score < 0 or score > 10 must exit 1.

4. **Invalid tier rejected:** JSON with a tier value not in {GOLD, SILVER, BRONZE, INVALID} must exit 1.

5. **Invalid judge name rejected:** JSON with a judge value not in {logic, consistency} must exit 1.

6. **Non-JSON rejected:** Non-JSON input (plain text) must exit 1.

7. **Empty input rejected:** Empty stdin must exit 1.

8. **Test script exits 0 on all-pass, non-zero on any failure.** Reports pass/fail count.

## Constraints
- Bash-only, no additional dependencies beyond jq (already required)
- Tests must be runnable standalone: `bash evals/tests/test_validate_output.sh`
- Each test case clearly labeled with description
