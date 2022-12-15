check:
	black --check .
	isort --check-only .
	flake8

format:
	black .
	isort .

lint:
	flake8

.PHONY: check format lint
