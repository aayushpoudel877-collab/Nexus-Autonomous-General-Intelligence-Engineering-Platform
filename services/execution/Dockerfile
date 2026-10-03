FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY services ./services
COPY packages ./packages
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "services.execution.worker"]
