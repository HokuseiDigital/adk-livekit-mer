FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install -e .

COPY *.py ./

# docker-compose overrides this with the right command per service
# (`python worker.py dev` or `uvicorn token_api:app …`).
CMD ["python", "worker.py", "dev"]
