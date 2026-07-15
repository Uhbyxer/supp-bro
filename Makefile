PYTHON ?= python3.11
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python

.PHONY: setup
setup:
	$(PYTHON) -m venv $(VENV)
	$(PYTHON_BIN) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Virtual environment is ready. Activate it with: source $(VENV)/bin/activate"
