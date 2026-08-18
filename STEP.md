
  STEP 7 of 7 — Shipping it

  New here:  A FastAPI service, AgentOS mounted onto it, a Dockerfile and CI.
  Run:       make lab4

  Next:      nothing — this is the finished app (same as main)

---

# Step 7 — Shipping it

**A FastAPI service, AgentOS mounted onto it, a Dockerfile and CI.**

## What to look at

- /health never calls the model — a health check that costs an API
- request reports your provider being down as you being down.
- The service starts with no API key and reports itself degraded
- rather than crash-looping.
- Three outcomes, three codes: 403 refused, 502 provider down, 200 ok.

## Commands

```bash
make lab4
make test        # the tests that exist at this step, no API key needed
make diff        # exactly what this step changed vs the previous one
make step        # this summary again
```

## Where this came from

```bash
git diff step-6-evals step-7-deploy -- src
```

That diff is the lesson. Everything else is unchanged.

## Getting unstuck

Nothing here is precious. If you break something:

```bash
git checkout .                  # undo your edits, keep the step
git switch step-7-deploy    # or jump back to a clean copy
git switch main                 # or straight to the finished app
```
