# SuppBro

Спочатку для пошуку потрібної інформації я використовував FAISS. Потім вирішив замінити його на MongoDB і Pinecone, але сама заміна технології майже нічого не покращила. Тоді я спробував два інші підходи: поєднав звичайний пошук за словами із пошуком за змістом, а також окремо додав модель, яка повторно сортує знайдені результати. Обидва варіанти допомогли знаходити правильну відповідь стабільніше. На останньому кроці я додав можливість одразу обмежувати пошук потрібним типом джерела — документацією або issues.

**SuppBro** is an assistant for support teams that helps triage and troubleshoot project issues with the right product context. The current project scope is related to the [Debezium](https://debezium.io/) open source project and uses Debezium documentation and GitHub project data as the first knowledge sources.

Debezium is a change data capture platform that streams database changes into event-driven systems. Teams use it to keep applications, caches, search indexes, analytics pipelines, and other downstream services in sync with database updates.

Support engineers often need to understand more than the ticket itself: which feature is affected, where the documentation lives, who owns the area, what recent changes may be related, and what troubleshooting steps are already known. **SuppBro** is intended to bring that context together so support teams can move from issue report to informed next action faster.

## Як покращувався retrieval

Після переходу з локального FAISS на MongoDB Atlas Vector Search і Pinecone стало зрозуміло, що сама заміна vector storage не вирішує проблему якості пошуку. Тому далі були реалізовані й порівняні два окремі способи покращення:

- **Cross-encoder reranking** — Pinecone спочатку знаходить 15 кандидатів, після чого cross-encoder повторно оцінює їх разом із запитом і формує фінальний Top-5.
- **Hybrid retrieval** — результати semantic search у Pinecone поєднуються з BM25 keyword search, а фінальний порядок Top-5 визначається за допомогою RRF.

В обох pipeline можна вибрати фільтр за metadata-полем `source`:

- порожнє значення — пошук одночасно в `pages` та `issues`;
- `pages` — пошук лише в документації;
- `issues` — пошук лише в GitHub issues.

Evaluation використовує однаковий набір із 10 запитів: 5 для документації та 5 для issues. Якщо вибрано конкретний `source`, оцінюються лише відповідні 5 запитів.

### Результати без фільтрації

| Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |
|---|---:|---:|---:|---:|
| Cross-encoder reranking | 80% | 100% | 0.90 | 58% |
| Hybrid BM25 + RRF | 80% | 100% | 0.90 | **62%** |

Обидва покращені підходи знаходять релевантний результат у Top-5 для всіх 10 запитів. За Top-1, Hit@5 і MRR вони показали однаковий результат. Hybrid retrieval має трохи вищий Precision@5, тобто частіше повертає додаткові релевантні chunks серед перших п’яти результатів.

Результати за типом джерела:

| Dataset | Pipeline | Top-1 | Hit@5 | MRR | Precision@5 |
|---|---|---:|---:|---:|---:|
| Pages | Cross-encoder reranking | 60% | 100% | 0.80 | 48% |
| Pages | Hybrid BM25 + RRF | 60% | 100% | 0.80 | **52%** |
| Issues | Cross-encoder reranking | 100% | 100% | 1.00 | 68% |
| Issues | Hybrid BM25 + RRF | 100% | 100% | 1.00 | **72%** |

Зараз hybrid retrieval показує найкращий загальний результат, хоча перевага невелика й проявляється лише в Precision@5. Для Issues значення Precision@5 треба трактувати обережно: для частини тестів релевантним вважається будь-який chunk правильного issue, тоді як для Pages expected chunks задані точніше.

## Goals

- Help support teams triage incoming project issues.
- Surface relevant feature context, documentation, owners, and stakeholders.
- Suggest likely troubleshooting paths based on known product information.
- Reduce repeated manual searching across docs, tickets, chats, and project history.
- Improve handoffs between support, engineering, product, and customer-facing teams.

## Debezium Resources

- [Debezium website](https://debezium.io/)
- [Debezium documentation](https://debezium.io/documentation/reference/stable/index.html)
- [Debezium GitHub organization](https://github.com/debezium)
- [Debezium main repository](https://github.com/debezium/debezium)
- [Debezium issue tracker](https://github.com/debezium/dbz/issues)
- [Debezium project board used by this repo](https://github.com/orgs/debezium/projects/5)

## Setup

This project uses Python 3.11, a local virtual environment, `pip`, and `make`.

Run the setup command:

```bash
make setup
```

The command creates `.venv`, upgrades `pip`, and installs dependencies from `requirements.txt`.

Activate the virtual environment before running Python commands:

```bash
source .venv/bin/activate
```

Downloading GitHub project issues requires the GitHub CLI. On macOS, install it with:

```bash
brew install gh
```

Download Debezium project issues into `data/hw1/raw/issues`:

```bash
gh auth login
make download-issues
```

## HW1 Knowledge Base

The HW1 data preparation scripts are documented in [scripts/hw1/KnowledgeBase_Readme.md](scripts/hw1/KnowledgeBase_Readme.md). They were created for [HW1_Knowledge_Base.md](https://github.com/Uhbyxer/RAG-1/blob/master/HW1_Knowledge_Base.md) and cover preparing normalized documents and chunks for the knowledge base.

## HW2 Semantic Index

The HW2 semantic search baseline is documented in [scripts/hw2/README.md](scripts/hw2/README.md). It builds a local FAISS index from the HW1 chunks and records retrieval checks for test queries.

## HW3 Retrieval Pipeline Improvements

The HW3 retrieval pipeline work is documented in [scripts/hw3/README.md](scripts/hw3/README.md). The first step moves semantic retrieval storage from the local FAISS baseline toward MongoDB Atlas Vector Search, with later space for comparing other retrieval backends such as Pinecone.
