# Architecting Autonomous Intelligence — workshop commands
#
#   make setup       install everything
#   make preflight   check your key and SDK work  <- run this first
#   make lab1..lab4  run each lab
#   make test        the test suite (works with NO API key)
#   make eval        the full eval suite (needs a key)
#   make serve       run the API
#
# Everything runs through .venv, so you never have to remember to activate it.

.DEFAULT_GOAL := help

# Linux and macOS put it in bin/, Windows (Git Bash) in Scripts/. Pick whichever
# exists, and fall back to the Unix path so the error message below reads right.
PY := $(firstword $(wildcard .venv/bin/python .venv/Scripts/python.exe) .venv/bin/python)
UV := $(shell command -v uv 2> /dev/null)

.PHONY: help setup preflight lab1 lab2 lab3 lab4 test test-live eval eval-json serve docker docker-build clean lint format check venv step diff steps

# Guard for every target that needs the virtualenv.
#
# Without this you get `make: .venv/bin/python: No such file or directory`,
# which is technically accurate and completely useless if you've just cloned
# the repo and don't yet know `make setup` is a thing.
venv:
	@test -x "$(PY)" || { \
	  echo ""; \
	  echo "  No Python environment found at .venv/"; \
	  echo ""; \
	  echo "  You haven't run setup yet. Do this first:"; \
	  echo ""; \
	  echo "      make setup"; \
	  echo ""; \
	  echo "  If that fails, you probably need uv:"; \
	  echo "      curl -LsSf https://astral.sh/uv/install.sh | sh"; \
	  echo ""; \
	  exit 1; }


# Some targets only make sense once the relevant step exists. On the workshop
# branch series (step-1-agent .. step-7-deploy) the code is built up one
# concept at a time, so "that file isn't here yet" is a normal state, not a
# broken checkout. Say which step it arrives at rather than dumping a
# traceback.
#   $(1) = file that must exist   $(2) = step that introduces it
define needs
	@test -e "$(1)" || { \
	  echo ""; \
	  echo "  Not available yet on this branch."; \
	  echo ""; \
	  echo "  $(1) arrives at $(2)."; \
	  echo "      git switch $(2)"; \
	  echo ""; \
	  echo "  Or jump to the finished app:   git switch main"; \
	  echo ""; \
	  exit 1; }
endef

# The soft version, for the SECOND half of a lab whose halves arrive at
# different steps. The first half has already run and succeeded, so a part
# that hasn't been introduced yet is a note, not a failed target.
#   $(1) = file   $(2) = step that introduces it   $(3) = banner for the part
define later
	@if [ -e "$(1)" ]; then \
	   echo ""; \
	   echo "  ── $(3) ──"; \
	   echo ""; \
	   $(PY) "$(1)"; \
	 else \
	   echo "  ($(1) arrives at $(2) — skipping that part.)"; \
	   echo ""; \
	 fi
endef

help:
	@echo ""
	@echo "  Architecting Autonomous Intelligence"
	@echo ""
	@echo "  Setup"
	@echo "    make setup        create the venv and install dependencies"
	@echo "    make preflight    verify your API key and SDK actually work"
	@echo ""
	@echo "  Labs"
	@echo "    make lab1         agent fundamentals   — the loop, by hand then with Agno"
	@echo "    make lab2         workflow design      — tools, structured output, routing"
	@echo "    make lab3         evaluation           — prove it works, then break it"
	@echo "    make lab4         deployment           — ship it as a service"
	@echo ""
	@echo "  Checks"
	@echo "    make test         run the tests        (no API key needed)"
	@echo "    make eval         run the eval suite   (needs an API key)"
	@echo "    make lint         ruff"
	@echo ""
	@echo "  Running it"
	@echo "    make serve        http://localhost:8000"
	@echo "    make docker       build and run the container"
	@echo "    make clean        delete generated databases and caches"
	@echo ""
	@echo "  Workshop branches"
	@echo "    make step         where am I, and what do I run next"
	@echo "    make diff         what this step changed vs the previous one"
	@echo "    make steps        list the step branches"
	@echo ""

setup:
ifndef UV
	@echo "uv is not installed. Get it with:"
	@echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
	@echo "(or see https://docs.astral.sh/uv/getting-started/installation/)"
	@exit 1
endif
	uv venv .venv --python 3.12
	uv pip install -e ".[dev]"
	@# Resolved here rather than using $(PY), which was evaluated before the
	@# virtualenv existed — and lives in Scripts/ on Windows, bin/ elsewhere.
	@VENV_PY=$$(test -x .venv/bin/python && echo .venv/bin/python || echo .venv/Scripts/python.exe); \
	 "$$VENV_PY" -m college_agent.data.seed
	@echo ""
	@echo "  Installed. Next:"
	@echo "    cp .env.example .env     # then paste your key into it"
	@echo "    make preflight"
	@echo ""

preflight: venv
	@$(PY) scripts/preflight.py

lab1: venv
	$(call needs,labs/lab1_fundamentals/01_raw_loop.py,step-3-tools)
	@# The raw loop is deliberately SDK-specific — the whole lesson is seeing it
	@# with no framework in the way — so there's one per provider. Same loop.
	@if [ "$$(grep -E '^COLLEGE_AGENT_PROVIDER=' .env 2>/dev/null | cut -d= -f2 | tr -d ' ')" = "openai" ]; then \
	   $(PY) labs/lab1_fundamentals/01_raw_loop_openai.py; \
	 else \
	   $(PY) labs/lab1_fundamentals/01_raw_loop.py; \
	 fi
	@echo ""
	@echo "  ── now the same thing with Agno ──"
	@echo ""
	@$(PY) labs/lab1_fundamentals/02_first_agent.py

lab2: venv
	$(call needs,labs/lab2_workflow/01_structured_triage.py,step-3-tools)
	@$(PY) labs/lab2_workflow/01_structured_triage.py
	$(call later,labs/lab2_workflow/02_routing_team.py,step-5-team,now with a router in front of specialists)

lab3: venv
	$(call needs,labs/lab3_eval/01_reliability.py,step-6-evals)
	@$(PY) labs/lab3_eval/01_reliability.py
	@echo ""
	@$(PY) labs/lab3_eval/02_accuracy.py
	@echo ""
	@$(PY) labs/lab3_eval/03_break_it.py

lab4: venv
	$(call needs,labs/lab4_deploy/01_call_the_api.py,step-7-deploy)
	@$(PY) labs/lab4_deploy/01_call_the_api.py

test: venv
	@$(PY) -m pytest -m "not live"

test-live: venv
	@$(PY) -m pytest

eval: venv
	$(call needs,evals/suite.py,step-6-evals)
	@$(PY) evals/suite.py

eval-json: venv
	@mkdir -p evals/results
	@$(PY) evals/suite.py --json-output evals/results/latest.json

serve: venv
	$(call needs,src/college_agent/api.py,step-7-deploy)
	@$(PY) -m college_agent.api

docker-build:
	$(call needs,Dockerfile,step-7-deploy)
	docker build -t college-triage:latest .

docker: docker-build
	docker run --rm -p 8000:8000 --env-file .env college-triage:latest

# Only the directories this branch actually has. labs/ and evals/ arrive
# partway through the step series, and `make lint` has to work on every
# branch — a linter that errors because a directory hasn't been introduced
# yet teaches students to ignore it.
SOURCES = $(wildcard src labs evals tests scripts)

lint: venv
	@$(PY) -m ruff check $(SOURCES)

format: venv
	@$(PY) -m ruff format $(SOURCES)
	@$(PY) -m ruff check --fix $(SOURCES)

check: lint test

step:
	@if [ -f STEP.md ]; then \
	   sed -n '1,/^---$$/p' STEP.md | sed '$$d'; \
	 else \
	   echo ""; echo "  No STEP.md — you're probably on main (the finished app)."; echo ""; \
	 fi
	@echo "  Branches:  $$(git branch --format='%(refname:short)' | grep '^step-' | tr '\n' ' ')"
	@echo ""

diff:
	@prev=$$(git branch --format='%(refname:short)' | grep '^step-' | sort | \
	         awk -v cur="$$(git rev-parse --abbrev-ref HEAD)" '$$0==cur{print p; exit} {p=$$0}'); \
	 if [ -z "$$prev" ]; then \
	   echo "No previous step — this is the first one."; \
	 else \
	   echo "Showing what this step changed, versus $$prev:"; echo ""; \
	   git --no-pager diff "$$prev" HEAD -- src labs evals tests; \
	 fi

steps:
	@git branch --format='%(refname:short)' | grep '^step-' | sed 's/^/  /'


clean:
	rm -rf .cache tmp .pytest_cache .ruff_cache evals/results
	rm -f src/college_agent/data/college.db agno.db *.db
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned. Run `make setup` or any lab to rebuild the database."
