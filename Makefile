PYTHON ?= python3.11
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python

.PHONY: setup download-issues build-index semantic-search build-mongo-index mongo-semantic-search
setup:
	$(PYTHON) -m venv $(VENV)
	$(PYTHON_BIN) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Virtual environment is ready. Activate it with: source $(VENV)/bin/activate"

download-issues:
	$(PYTHON_BIN) scripts/hw1/download_project_issues.py

build-index:
	$(PYTHON_BIN) scripts/hw2/build_index.py

semantic-search:
	$(PYTHON_BIN) scripts/hw2/semantic_search.py

build-mongo-index:
	$(PYTHON_BIN) scripts/hw3/build_mongo_vector_index.py

mongo-semantic-search:
	$(PYTHON_BIN) scripts/hw3/mongo_semantic_search.py
