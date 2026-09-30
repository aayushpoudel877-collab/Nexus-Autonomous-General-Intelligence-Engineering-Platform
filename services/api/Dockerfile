FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY services ./services
COPY packages ./packages
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
