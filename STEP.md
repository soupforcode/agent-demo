
  STEP 1 of 7 — An agent

  New here:  A model, some instructions, and nothing else. No tools, no schema.
  Run:       python -m college_agent.agent

  Next:      git switch step-2-structured

---

# Step 1 — An agent

**A model, some instructions, and nothing else. No tools, no schema.**

## What to look at

- It answers in prose — readable, but no system can route on it.
- It has no way to look up CS22B007, so anything it says about that
- student is invented. Both problems get fixed, one per step.

## Commands

```bash
python -m college_agent.agent
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-1-agent    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
