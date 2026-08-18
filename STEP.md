
  STEP 2 of 7 — A contract

  New here:  output_schema=TriageResult — one parameter.
  Run:       python -m college_agent.agent

  Next:      git switch step-3-tools

---

# Step 2 — A contract

**output_schema=TriageResult — one parameter.**

## What to look at

- You now get a validated object you could route, count and test.
- It is also still invented — the agent has no tools yet. Structure
- buys parseability, not truth, and it makes a wrong answer look
- considerably more authoritative than prose did.

## Commands

```bash
python -m college_agent.agent
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Where this came from

```bash
git diff step-1-agent step-2-structured -- src
```

That diff is the lesson. Everything else is unchanged.

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-2-structured    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
