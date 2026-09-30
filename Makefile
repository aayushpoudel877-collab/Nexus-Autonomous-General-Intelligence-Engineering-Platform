install:
	python -m pip install -e '.[dev]'
api:
	uvicorn services.api.app.main:app --reload --port 8000
test:
	pytest
lint:
	ruff check .
