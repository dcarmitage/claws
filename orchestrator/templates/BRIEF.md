You have ONE task. Do it precisely, validate, commit, done.

**Task:** [name]

**File:** [path] — [scope constraint, e.g. "WATCH_HTML only" or "Python functions only"]

**Changes:**
[Exact code to write or precise description of changes.
Include surrounding context so the builder knows WHERE to insert.
The more specific, the better.]

**DO NOT** modify [out-of-scope areas].

**Validate:**
```bash
[validation commands that MUST pass]
```

**Commit:**
```bash
cd $CLAWS_HOME && git add [files] && git commit -m "[message]"
```

Report PASS or FAIL with the validation output.
