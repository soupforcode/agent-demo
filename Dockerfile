# Two stages: build the dependencies once, then copy only what's needed to run.
# The result is a smaller image and, more importantly, a layer cache that means
# changing your prompt doesn't reinstall PyTorch-sized dependency trees.

FROM python:3.12-slim AS builder

# uv is dramatically faster than pip here, which you notice when you're
# rebuilding an image for the fifth time in a workshop.
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

WORKDIR /build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first, source second. Docker caches layers in order, so editing
# agent.py doesn't invalidate the dependency install.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN uv venv /opt/venv --python 3.12 \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache .


FROM python:3.12-slim AS runtime

# Don't run as root. Nothing in here needs it, and a container that doesn't
# need root shouldn't have it.
RUN useradd --create-home --uid 1000 app

COPY --from=builder --chown=app:app /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    AGNO_TELEMETRY=false

WORKDIR /app
COPY --chown=app:app src/ ./src/
USER app

# Build the college database at image build time so the first request doesn't
# pay for it.
RUN python -c "import sys; sys.path.insert(0,'src'); from college_agent.data.seed import build; build(quiet=True)"

ENV PYTHONPATH=/app/src

EXPOSE 8000

# /health answers from configuration alone and never calls the model, so this
# check is free and won't report Google being down as us being down.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "college_agent.api"]
