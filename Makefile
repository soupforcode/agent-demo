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
PY := .venv/bin/python
UV := $(shell command -v uv 2> /dev/null)

.PHONY: help setup preflight lab1 lab2 lab3 lab4 test eval serve docker docker-build clean lint format check

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

setup:
ifndef UV
	@echo "uv is not installed. Get it with:"
	@echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
	@echo "(or see https://docs.astral.sh/uv/getting-started/installation/)"
	@exit 1
endif
	uv venv .venv --python 3.12
	uv pip install -e ".[dev]"
	@$(PY) -m college_agent.data.seed
	@echo ""
	@echo "  Installed. Next:"
	@echo "    cp .env.example .env     # then paste your key into it"
	@echo "    make preflight"
	@echo ""

preflight:
	@$(PY) scripts/preflight.py

lab1:
	@$(PY) labs/lab1_fundamentals/01_raw_loop.py
	@echo ""
	@echo "  ── now the same thing with Agno ──"
	@echo ""
	@$(PY) labs/lab1_fundamentals/02_first_agent.py

lab2:
	@$(PY) labs/lab2_workflow/01_structured_triage.py
	@echo ""
	@echo "  ── now with a router in front of specialists ──"
	@echo ""
	@$(PY) labs/lab2_workflow/02_routing_team.py

lab3:
	@$(PY) labs/lab3_eval/01_reliability.py
	@echo ""
	@$(PY) labs/lab3_eval/02_accuracy.py
	@echo ""
	@$(PY) labs/lab3_eval/03_break_it.py

lab4:
	@$(PY) labs/lab4_deploy/01_call_the_api.py

test:
	@$(PY) -m pytest -m "not live"

test-live:
	@$(PY) -m pytest

eval:
	@$(PY) evals/suite.py

eval-json:
	@mkdir -p evals/results
	@$(PY) evals/suite.py --json-output evals/results/latest.json

serve:
	@$(PY) -m college_agent.api

docker-build:
	docker build -t college-triage:latest .

docker: docker-build
	docker run --rm -p 8000:8000 --env-file .env college-triage:latest

lint:
	@$(PY) -m ruff check src labs evals tests scripts

format:
	@$(PY) -m ruff format src labs evals tests scripts
	@$(PY) -m ruff check --fix src labs evals tests scripts

check: lint test

clean:
	rm -rf .cache tmp .pytest_cache .ruff_cache evals/results
	rm -f src/college_agent/data/college.db agno.db *.db
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned. Run `make setup` or any lab to rebuild the database."
