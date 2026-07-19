# HW1: підготовка бази знань

Загальний опис проєкту SuppBro є в [головному README](../../README.md).

## Джерела знань

Для HW1 використовуються два основні джерела знань:

- документація Debezium: [Debezium documentation 3.6](https://debezium.io/documentation/reference/3.6/). Вона відповідає файлам у GitHub-репозиторії Debezium, де сторінки документації зберігаються у форматі AsciiDoc: [documentation/modules/ROOT/pages](https://github.com/debezium/debezium/tree/3.6/documentation/modules/ROOT/pages);
- GitHub issues з Debezium project board, які завантажуються в JSONL-формат і використовуються як приклади реальних запитів, багів та обговорень: https://github.com/orgs/debezium/projects/5

## Потік даних

```text
data/hw1/raw
  -> scripts/hw1/prepare_knowledge_base.py
  -> data/hw1/processed/normalized_documents.jsonl
  -> scripts/hw1/chunk_documents.py
  -> data/hw1/processed/chunks_large.jsonl
  -> data/hw1/processed/chunks_medium.json
```

`download_project_issues.py` використовується тільки для отримання GitHub issues перед підготовкою бази знань. Основний пайплайн HW1 складається з двох кроків: нормалізація документів і chunking.

## Підготовка джерел

`prepare_knowledge_base.py` читає файли з `data/hw1/raw` і створює нормалізовані документи в `data/hw1/processed/normalized_documents.jsonl`.

Скрипт підтримує такі типи джерел:

- `.adoc` файли документації Debezium;
- `.md` Markdown-файли;
- `.csv` табличні дані;
- налаштований JSONL-файл GitHub issues: `data/hw1/raw/issues/debezium-project-5.jsonl`.

Для AsciiDoc скрипт робить невелику нормалізацію: прибирає службові атрибути, обробляє прості умовні блоки, підставляє відомі атрибути на кшталт `{prodname}`. Для GitHub issues беруться перші записи з JSONL-файлу, щоб показати, як issue теж може стати документом знань.

Приклад запуску з кореня репозиторію:

```bash
source .venv/bin/activate
python scripts/hw1/prepare_knowledge_base.py
```

Приклади нормалізованих JSONL-записів з обох джерел:

```json
[
  {
    "document_id": "pages:configuration:storage",
    "source_file": "data/hw1/raw/pages/configuration/storage.adoc",
    "source_type": "asciidoc",
    "title": "Storage",
    "text": "= Storage\n\n== Overview\n...",
    "metadata": {
      "language": "en",
      "source": "pages",
      "feature": "configuration"
    }
  },
  {
    "document_id": "issues:dbz:1407",
    "source_file": "data/hw1/raw/issues/debezium-project-5.jsonl",
    "source_type": "markdown",
    "title": "Postgres connector log position validation logic is flawed [DBZ-9535]",
    "text": "# Postgres connector log position validation logic is flawed [DBZ-9535]\n\nMigrated from [DBZ-9535](https://issues.redhat.com/browse/DBZ-9535)\n...",
    "metadata": {
      "language": "en",
      "source": "issues",
      "feature": "dbz"
    }
  }
]
```

Ключові поля:

- `document_id` - стабільний ідентифікатор документа;
- `source_file` - шлях до сирого джерела;
- `source_type` - тип початкового вмісту після читання;
- `title` - назва документа;
- `text` - нормалізований текст;
- `metadata` - службові ознаки для подальшого chunking та індексації.

## Chunking документів

`chunk_documents.py` читає `data/hw1/processed/normalized_documents.jsonl` і створює два файли: `data/hw1/processed/chunks_large.jsonl` для page chunks і `data/hw1/processed/chunks_medium.json` для issue chunks.

Скрипт використовує різну логіку для різних джерел:

- `metadata.source = "pages"`: документ ділиться на large chunks за верхньорівневими AsciiDoc-секціями `== ...`; секція `Overview` використовується як кореневий chunk і додається як overlap до інших секцій; результат записується в `chunks_large.jsonl`;
- `metadata.source = "issues"`: issue ділиться на medium chunks по 700 символів з overlap 150 символів.

Приклад запуску з кореня репозиторію:

```bash
source .venv/bin/activate
python scripts/hw1/chunk_documents.py
```

Приклади chunk-записів з обох джерел:

```json
[
  {
    "chunk_id": "pages:configuration:storage:overview",
    "size": "large",
    "text": "== Overview\n\nDebezium supports several ways to store connector state...",
    "metadata": {
      "document_id": "pages:configuration:storage",
      "source_file": "data/hw1/raw/pages/configuration/storage.adoc",
      "source_type": "asciidoc",
      "title": "Storage",
      "language": "en",
      "source": "pages",
      "feature": "configuration",
      "chunk_index": 1,
      "prev_chunk_id": null,
      "next_chunk_id": "pages:configuration:storage:file_system_storage",
      "root_chunk_id": "pages:configuration:storage:overview"
    }
  },
  {
    "chunk_id": "issues:dbz:1407:chunk_001",
    "size": "medium",
    "text": "# Postgres connector log position validation logic is flawed...",
    "metadata": {
      "document_id": "issues:dbz:1407",
      "source_file": "data/hw1/raw/issues/debezium-project-5.jsonl",
      "source_type": "markdown",
      "title": "Postgres connector log position validation logic is flawed [DBZ-9535]",
      "language": "en",
      "source": "issues",
      "feature": "dbz",
      "chunk_index": 1,
      "prev_chunk_id": null,
      "next_chunk_id": "issues:dbz:1407:chunk_002",
      "root_chunk_id": "issues:dbz:1407:chunk_001"
    }
  }
]
```

Навігаційні поля в `metadata` допомагають відновлювати контекст:

- `prev_chunk_id` - попередній chunk того самого документа або `null`;
- `next_chunk_id` - наступний chunk того самого документа або `null`;
- `root_chunk_id` - головний chunk документа.

## Повний приклад

Якщо в `data/hw1/raw/issues` ще немає issue-даних, спочатку потрібно авторизувати GitHub CLI і завантажити issues:

```bash
gh auth login
make download-issues
```

Після цього можна побудувати нормалізовані документи і chunks:

```bash
source .venv/bin/activate
python scripts/hw1/prepare_knowledge_base.py
python scripts/hw1/chunk_documents.py
```

Очікувані результати:

- `data/hw1/processed/normalized_documents.jsonl` - єдиний формат документів;
- `data/hw1/processed/chunks_large.jsonl` - large chunks з документації Debezium;
- `data/hw1/processed/chunks_medium.json` - medium chunks з GitHub issues для наступного етапу RAG.

## Висновок

В роботі використовується дві різні chunking-стратегії залежно від `metadata.source`.
Для `pages` враховується структура документації: документ ділиться за AsciiDoc-секціями, а секція `Overview` додається як контекст до інших chunks.
Для `issues` використовується простіша стратегія: фіксований розмір chunk по 700 символів з overlap 150 символів.

Це дає різну поведінку для різних типів знань:

- page chunks зберігають структуру документа і краще передають контекст секції;
- issue chunks мають стабільний розмір і простіше контролюються для індексації;
- page chunks іноді виходять дуже великими, бо окремі секції документації можуть бути довгими;
- issue chunks не враховують внутрішню структуру issue, наприклад заголовки, блоки логів або секції bug report.

Що варто покращити:

- для `pages` додати додаткове дробіння великих секцій на менші chunks, зберігаючи прив'язку до батьківської секції і `Overview`;
- для `issues` зробити структурну стратегію chunking, яка враховує Markdown/Jira-заголовки, блоки коду, логи та типові секції issue, а не тільки фіксований overlap.

Поточні розміри large chunks:

```text
- pages:configuration:eos:overview: 742 symbols
- pages:configuration:eos:kafka_connect_exactly_once_support_for_source_connector: 2262 symbols
- pages:configuration:eos:debezium_connectors_supporting_exactly_once_delivery: 970 symbols
- pages:configuration:eos:configuration: 1282 symbols
- pages:configuration:storage:overview: 973 symbols
- pages:configuration:storage:kafka: 4709 symbols
- pages:configuration:storage:file: 1861 symbols
- pages:configuration:storage:memory: 1366 symbols
- pages:configuration:storage:jdbc: 14008 symbols
- pages:configuration:storage:redis: 15978 symbols
- pages:configuration:storage:amazon_s3: 2128 symbols
- pages:configuration:storage:azure_blob_storage: 2715 symbols
- pages:configuration:storage:rocketmq: 3118 symbols
- pages:configuration:storage:chronicle_queue: 4172 symbols
```

Поточні розміри medium chunks:

```text
- issues:dbz:1407:chunk_001: 700 symbols
- issues:dbz:1407:chunk_002: 700 symbols
- issues:dbz:1407:chunk_003: 700 symbols
- issues:dbz:1407:chunk_004: 700 symbols
- issues:dbz:1407:chunk_005: 699 symbols
- issues:dbz:1407:chunk_006: 700 symbols
- issues:dbz:1407:chunk_007: 700 symbols
- issues:dbz:1407:chunk_008: 700 symbols
- issues:dbz:1407:chunk_009: 700 symbols
- issues:dbz:1407:chunk_010: 700 symbols
- issues:dbz:1407:chunk_011: 700 symbols
- issues:dbz:1407:chunk_012: 234 symbols
- issues:dbz:11:chunk_001: 87 symbols
- issues:dbz:4:chunk_001: 699 symbols
- issues:dbz:4:chunk_002: 700 symbols
- issues:dbz:4:chunk_003: 700 symbols
- issues:dbz:4:chunk_004: 700 symbols
- issues:dbz:4:chunk_005: 700 symbols
- issues:dbz:4:chunk_006: 332 symbols
- issues:dbz:3:chunk_001: 700 symbols
- issues:dbz:3:chunk_002: 700 symbols
- issues:dbz:3:chunk_003: 699 symbols
- issues:dbz:3:chunk_004: 700 symbols
- issues:dbz:3:chunk_005: 699 symbols
- issues:dbz:3:chunk_006: 699 symbols
- issues:dbz:3:chunk_007: 700 symbols
- issues:dbz:3:chunk_008: 700 symbols
- issues:dbz:3:chunk_009: 700 symbols
- issues:dbz:3:chunk_010: 700 symbols
- issues:dbz:3:chunk_011: 699 symbols
- issues:dbz:3:chunk_012: 149 symbols
- issues:dbz:73:chunk_001: 700 symbols
- issues:dbz:73:chunk_002: 700 symbols
- issues:dbz:73:chunk_003: 700 symbols
- issues:dbz:73:chunk_004: 700 symbols
- issues:dbz:73:chunk_005: 700 symbols
- issues:dbz:73:chunk_006: 700 symbols
- issues:dbz:73:chunk_007: 700 symbols
- issues:dbz:73:chunk_008: 700 symbols
- issues:dbz:73:chunk_009: 698 symbols
- issues:dbz:73:chunk_010: 283 symbols
```
