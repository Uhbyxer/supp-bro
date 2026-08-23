# BMad Architecture Reviewer Gate: Current Tech Reality

Review target: `_bmad-output/planning-artifacts/architecture/architecture-SuppBro-2026-08-23/ARCHITECTURE-SPINE.md`

Lens: verify every committed decision was web-researched or reality-checked rather than asserted from training data: current library/framework versions, named technology existence and fit, and brownfield fit with the existing project.

## Verdict

**PASS WITH REQUIRED FOLLOW-UP**

The spine is broadly grounded in the existing SuppBro repo and the named framework choices are real, current enough, and compatible with Python 3.11. The architectural direction also matches the brownfield direction in `AGENTS.md`: move useful behavior out of homework scripts into `src/supp_bro/` without growing `scripts/hw*`.

Required follow-up is documentation-level, not a blocker to proceeding: add explicit evidence notes for the Stack table and clarify current-vs-deferred retrieval backends so future implementers do not read the spine as a researched long-term backend choice.

## Evidence Checked

### Repo Reality

- `ARCHITECTURE-SPINE.md` declares a future product package under `src/supp_bro/`, while the repo currently has no `src/` directory. This is consistent with `AGENTS.md`, which says new product code should go under `src/supp_bro/` when package structure is introduced.
- `README.md` states the project uses Python 3.11, a local virtual environment, `pip`, and `make`.
- `Makefile` uses `python3.11` by default and runs all current commands through `.venv/bin/python`.
- `requirements.txt` pins or lower-bounds every dependency named in the spine: `openai>=1.80.0`, `langgraph>=1.0.0`, `pinecone>=7.0.0`, `streamlit>=1.37.0`.
- Current scripts still use homework-era modules and local path imports, especially HW3-HW7. The proposed package boundaries are therefore an intended migration target, not current state.
- The existing workflow route names in the spine match HW6/HW7 product routes: `docs_answer`, `issue_investigation`, `community_lookup`, and `clarification`.
- The secret rule for `MONGODB_URI` is consistent with `AGENTS.md` and current Mongo scripts.

### Primary / Official Docs Reality Check

- Python 3.11 is still supported, but in security mode until October 2027 according to the official Python Developer Guide version status page.
- LangGraph is current and production/stable on PyPI; official LangChain docs describe LangGraph v1 as a stability-focused release that preserves core graph APIs and execution model. The repo's current HW7 uses `StateGraph`, nodes, edges, and conditional routing, so LangGraph remains a fit for the stated workflow role.
- Streamlit `1.37.0` exists on PyPI and has official release notes; newer releases exist, but `>=1.37.0` is a valid lower bound for a local demo UI.
- OpenAI Python SDK `1.80.0` exists in the official `openai-python` release history/PyPI history. The repo currently uses `OpenAI(...)` in HW4 RAG answer generation.
- Pinecone Python SDK v7 exists and is mapped by Pinecone docs to the `2025-04` API version; the docs state the `pinecone` package is the Python SDK package name. Current HW3/HW4 scripts import `Pinecone` and use Pinecone indexes, so the dependency is real and fitting.
- GitHub REST Issues endpoints are current in official GitHub docs and fit the existing HW5/HW6/HW7 issue investigation behavior.
- Stack Exchange `/search` is current in official Stack Exchange API docs and fits the existing Stack Overflow community lookup behavior.
- MongoDB Atlas Vector Search / PyMongo SearchIndexModel docs are current and fit the repo's HW3 Mongo vector work, even though the architecture spine defers backend consolidation.

## Findings

### 1. Medium: Stack omits current brownfield dependencies that remain architecturally relevant.

`ARCHITECTURE-SPINE.md` lists only Python, LangGraph, Streamlit, OpenAI, and Pinecone in the Stack table. The repo still has committed brownfield retrieval dependencies and scripts for FAISS, MongoDB/PyMongo, sentence-transformers, rank-bm25, numpy, python-dotenv, and tiktoken in `requirements.txt`.

This matters because the spine also says first product slices should wrap current HW4/HW3 behavior before choosing a long-term retrieval backend. If the Stack table is used as the implementation contract, a future builder could incorrectly treat FAISS/Mongo/local embeddings as outside the researched baseline even though they are part of the existing project reality.

Recommended fix: split Stack into `Product target stack` and `Brownfield dependencies to wrap or retire`, or add a note that the table lists only forward product commitments while HW2/HW3 dependencies remain migration inputs.

### 2. Medium: Provider normalization names future provider payloads without a current decision record.

The convention row says GitHub, Stack Overflow, Pinecone, OpenAI, and future provider payloads are normalized before entering workflow state. GitHub, Stack Overflow, Pinecone, and OpenAI are grounded in current scripts and official docs. The phrase "future provider payloads" is intentionally broad but is not a committed technology choice.

This is acceptable as an architectural rule, but it should not be read as research-backed approval of unnamed future providers. The decision should be framed as a boundary invariant, not as a technology commitment.

Recommended fix: revise to "Any provider payload used by an adapter must be normalized..." and keep the current providers as examples.

### 3. Low: Python 3.11 is valid but already security-only.

The Python 3.11 stack decision matches `README.md`, `Makefile`, and supported dependency ranges. Official Python status shows 3.11 is security-only and reaches end-of-life in October 2027.

This is not a blocker for a brownfield local quick-dev repo, but the spine should record that Python 3.11 is a compatibility baseline, not a fresh long-term runtime recommendation.

Recommended fix: add an evidence note beside Python 3.11: "matches repo; supported in security mode through 2027-10."

### 4. Low: Version lower bounds are current enough, but the spine has no visible research trail.

The version lower bounds in `requirements.txt` and the spine check out against official or primary package docs. However, the architecture file itself has no citations or `.memlog` evidence for how these versions were chosen.

Recommended fix: add a short "Tech reality notes" section or companion evidence file with official-doc links and the repo files that justify each row. That will make this reviewer gate reproducible.

## Gate Notes

- I did not find a named technology in the spine that no longer exists.
- I did not find a framework version that is incompatible with the repo's Python 3.11 baseline.
- I did not find brownfield decisions that contradict `AGENTS.md`; the package migration direction is consistent with the project instructions.
- The only required action before using this as a durable architecture artifact is to make the researched status explicit and avoid implying Pinecone-only retrieval while Mongo/FAISS still exist in the repo history.

## Sources Used

Repo files:

- `AGENTS.md`
- `README.md`
- `Makefile`
- `requirements.txt`
- `scripts/hw3/*`
- `scripts/hw4/rag_answer.py`
- `scripts/hw5/external_tool_router.py`
- `scripts/hw6/agentic_workflow.py`
- `scripts/hw7/langgraph_flow.py`
- `scripts/hw7/streamlit_app.py`
- `scripts/hw6/test_agentic_workflow.py`
- `scripts/hw7/test_langgraph_flow.py`

Official / primary docs:

- Python Developer Guide, Status of Python versions: https://devguide.python.org/versions/
- LangGraph v1 docs: https://docs.langchain.com/oss/python/releases/langgraph-v1
- LangGraph PyPI: https://pypi.org/project/langgraph/
- Streamlit PyPI release history: https://pypi.org/project/streamlit/1.37.0/
- Streamlit official 1.37.0 announcement: https://discuss.streamlit.io/t/version-1-37-0/75769
- OpenAI Python SDK GitHub releases / PyPI history: https://github.com/openai/openai-python/releases and https://pypi.org/project/openai/
- Pinecone Python SDK docs: https://docs.pinecone.io/reference/sdks/python/overview
- GitHub REST Issues docs: https://docs.github.com/en/rest/issues
- Stack Exchange API `/search` docs: https://api.stackexchange.com/docs/search
- MongoDB PyMongo / Atlas Search and Vector Search docs: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/atlas-search/
