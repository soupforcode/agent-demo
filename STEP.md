
  STEP 4 of 7 — Guardrails

  New here:  Checks that run before the model — PII, and third-party record requests.
  Run:       make test

  Next:      git switch step-5-team

---

# Step 4 — Guardrails

**Checks that run before the model — PII, and third-party record requests.**

## What to look at

- An instruction is advice; a guardrail is a rule. The agent was
- already told to refuse third-party requests. Now it cannot comply
- even if a cleverly worded ticket talks it into trying.
- They run before the API call, so a blocked ticket costs zero quota.

## Commands

```bash
make test
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Where this came from

```bash
git diff step-3-tools step-4-guardrails -- src
```

That diff is the lesson. Everything else is unchanged.

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-4-guardrails    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
