# Two stages: resolve and install dependencies once, then ship only the
# resulting virtualenv. Keeps the runtime image small and, more usefully, means
# editing a prompt doesn't reinstall the whole dependency tree.

FROM python:3.12-slim AS builder

# uv rather than pip — noticeably faster, which you feel by the fifth rebuild.
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

WORKDIR /build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml README.md ./
COPY src/ ./src/

# A real (non-editable) install, so the runtime stage needs the venv and
# nothing else — one copy of the code, not two.
RUN uv venv /opt/venv --python 3.12 \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache .


FROM python:3.12-slim AS runtime

# Nothing here needs root, so nothing here runs as root.
RUN useradd --create-home --uid 1000 app

COPY --from=builder --chown=app:app /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    AGNO_TELEMETRY=false

WORKDIR /app
USER app

# Build the college database now, so the first request doesn't pay for it.
RUN python -c "from college_agent.data.seed import build; build(quiet=True)"

EXPOSE 8000

# /health answers from configuration alone and never calls the model, so this
# probe is free and won't report Google being down as us being down.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "college_agent.api"]
