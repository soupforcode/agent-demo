
  STEP 6 of 7 — Proving it works

  New here:  Ten golden cases, tool-call reliability, and a deliberate sabotage.
  Run:       make lab3

  Next:      git switch step-7-deploy

---

# Step 6 — Proving it works

**Ten golden cases, tool-call reliability, and a deliberate sabotage.**

## What to look at

- Reliability first: did it look things up, or get lucky? That check
- is free and deterministic, and catches what accuracy scoring cannot.
- Then break the agent on purpose. If the score does not move, your
- eval suite is decoration.

## Commands

```bash
make lab3
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Where this came from

```bash
git diff step-5-team step-6-evals -- src
```

That diff is the lesson. Everything else is unchanged.

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-6-evals    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
