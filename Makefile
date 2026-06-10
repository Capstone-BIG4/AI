.PHONY: dev check check-artifacts check-python

PYTHON ?= python

dev:
	$(PYTHON) scripts/dev/run_server.py --port 8000

check: check-python check-artifacts

check-python:
	$(PYTHON) -m py_compile backend/app/main.py backend/app/api/router.py backend/app/pipeline/executor.py scripts/check_artifacts.py scripts/check_manifest_paths.py

check-artifacts:
	$(PYTHON) scripts/check_artifacts.py
	$(PYTHON) scripts/check_manifest_paths.py
	$(PYTHON) scripts/check_token_leaks.py
