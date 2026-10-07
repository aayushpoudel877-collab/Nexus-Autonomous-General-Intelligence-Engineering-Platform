FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY services ./services
COPY packages ./packages
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "services.orchestrator.worker"]
