PYTHON ?= python3.11
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python

.PHONY: setup download-issues build-index semantic-search build-mongo-index mongo-semantic-search build-pinecone-index pinecone-semantic-search pinecone-retrieval-evaluation pinecone-hybrid-evaluation rag-answer hw5-external-tool hw6-agentic-workflow hw6-streamlit hw7-langgraph-workflow hw7-streamlit final-langgraph-workflow final-test final-streamlit final-retrieval-eval final-workflow-eval final-ragas-eval
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

build-pinecone-index:
	$(PYTHON_BIN) scripts/hw3/build_pinecone_vector_index.py

pinecone-semantic-search:
	$(PYTHON_BIN) scripts/hw3/pinecone_semantic_search.py

pinecone-retrieval-evaluation:
	$(PYTHON_BIN) scripts/hw3/pinecone_retrieval_evaluation.py

pinecone-hybrid-evaluation:
	$(PYTHON_BIN) scripts/hw3/pinecone_hybrid_evaluation.py

rag-answer:
	$(PYTHON_BIN) scripts/hw4/rag_answer.py $(if $(SOURCE),--source $(SOURCE),) "$(QUESTION)"

hw5-external-tool:
	$(PYTHON_BIN) scripts/hw5/external_tool_router.py "$(QUESTION)"

hw6-agentic-workflow:
	$(PYTHON_BIN) scripts/hw6/agentic_workflow.py "$(QUESTION)"

hw6-streamlit:
	$(PYTHON_BIN) -m streamlit run scripts/hw6/streamlit_app.py

hw7-langgraph-workflow:
	$(PYTHON_BIN) scripts/hw7/langgraph_flow.py "$(QUESTION)"

hw7-streamlit:
	$(PYTHON_BIN) -m streamlit run scripts/hw7/streamlit_app.py

final-langgraph-workflow:
	$(PYTHON_BIN) scripts/final/langgraph_flow.py "$(QUESTION)"

final-test:
	$(PYTHON_BIN) -m unittest scripts/final/test_langgraph_flow.py

final-streamlit:
	$(PYTHON_BIN) -m streamlit run scripts/final/streamlit_app.py

final-retrieval-eval:
	PINECONE_HYBRID_JSON_PATH=scripts/final/outputs/eval_retrieval_results.json PINECONE_HYBRID_SUMMARY_PATH=scripts/final/outputs/eval_retrieval_results.md $(PYTHON_BIN) scripts/hw3/pinecone_hybrid_evaluation.py

final-workflow-eval:
	$(PYTHON_BIN) scripts/final/evals/run_workflow_eval.py $(if $(MIN_VECTOR_SCORE),--min-vector-score $(MIN_VECTOR_SCORE),)

final-ragas-eval:
	$(PYTHON_BIN) scripts/final/evals/run_ragas_eval.py $(if $(MIN_VECTOR_SCORE),--min-vector-score $(MIN_VECTOR_SCORE),)
