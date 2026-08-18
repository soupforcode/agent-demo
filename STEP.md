
  STEP 5 of 7 — One agent, or several

  New here:  A router in front of three specialists.
  Run:       make lab2

  Next:      git switch step-6-evals

---

# Step 5 — One agent, or several

**A router in front of three specialists.**

## What to look at

- This is a comparison, not an upgrade. The team roughly doubles
- your model calls — router, then specialist.
- Ask honestly whether it did better, or just cost more. For six
- tools and one domain, one agent is usually enough.

## Commands

```bash
make lab2
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Where this came from

```bash
git diff step-4-guardrails step-5-team -- src
```

That diff is the lesson. Everything else is unchanged.

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-5-team    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
