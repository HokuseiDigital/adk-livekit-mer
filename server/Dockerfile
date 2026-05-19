FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/venv \
    PATH="/venv/bin:$PATH"

WORKDIR /app

# Install uv. Pinning the version keeps reproducibility tight; bump it
# intentionally rather than letting `latest` drift across builds.
COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY *.py ./
RUN uv sync --frozen

# Bake Silero VAD + multilingual turn detector model weights into the
# image. Without this, the first job crashes because MultilingualModel
# tries to load files from a local HF cache that doesn't exist yet, and
# the livekit-agents inference subprocess won't auto-download. Doing
# it at build time costs ~30 MB and removes the one-time
# `download-files` step from the docker quick-start.
RUN uv run python worker.py download-files

# docker-compose overrides this with the right command per service
# (`python worker.py dev` or `uvicorn token_api:app …`).
CMD ["python", "worker.py", "dev"]
