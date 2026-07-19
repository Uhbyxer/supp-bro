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

`chunk_documents.py` читає `data/hw1/processed/normalized_documents.jsonl` і створює `data/hw1/processed/chunks_medium.json`.

Скрипт використовує різну логіку для різних джерел:

- `metadata.source = "pages"`: документ ділиться за верхньорівневими AsciiDoc-секціями `== ...`; секція `Overview` використовується як кореневий chunk і додається як overlap до інших секцій;
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
    "size": "medium",
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
- `data/hw1/processed/chunks_medium.json` - medium chunks для наступного етапу RAG.
