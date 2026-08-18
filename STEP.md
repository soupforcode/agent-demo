
  STEP 3 of 7 — Tools

  New here:  Six tools over the college database, and the agent that uses them.
  Run:       make lab2

  Next:      git switch step-4-guardrails

---

# Step 3 — Tools

**Six tools over the college database, and the agent that uses them.**

## What to look at

- Now it looks things up. The hall-ticket ticket should route to
- accounts, not examinations — the block is unpaid fees, and only
- the tool call reveals that.
- Read the docstrings in tools.py: they are prompt text, not comments.

## Commands

```bash
make lab2
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Where this came from

```bash
git diff step-2-structured step-3-tools -- src
```

That diff is the lesson. Everything else is unchanged.

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-3-tools    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
