---
marp: true
theme: default
paginate: true
---

# Контекст

![width:1050px](assets/team-routing.svg)

**Кілька Customer teams → одна Support team → кілька Product teams**

---

# Проблема

- Причина issue часто неочевидна.
- **Bug / configuration / known limitation?**
- Якщо bug — **яка Product team відповідає?**
- Support шукає документацію, старі issues та схожі кейси.
- Product teams отримують запити, які можна відфільтрувати раніше.

> Support потрібен швидкий спосіб зібрати контекст і правильно маршрутизувати проблему.

---

# Ідея: POC Support Bot

- Швидко збирає **контекст проблеми**.
- Знає **активні features та ownership**.
- Робить первинний **issue triage**.
- Шукає **схожі кейси інших клієнтів**.
- Визначає: **bug / config / limitation / known issue**.
- Підказує, чи можна вирішити проблему **без Product team**.

> Мета — швидше зрозуміти проблему і правильно її маршрутизувати.

---

# POC Scope: Debezium

Open-source **Debezium** + 2 джерела знань:

- **Documentation** — [Debezium Docs](https://debezium.io/documentation/reference/stable/)
- **Issue Tracker** — [Debezium GitHub Issues](https://github.com/debezium/dbz/issues)

**Docs:** features, configuration, limitations  
**Issues:** bugs, known problems, workarounds

---

# Knowledge Ingestion

**Documentation / Issues → Chunking → Embeddings → Pinecone Index**

- Контент розбивається на **chunks**.
- Для chunks створюються **embeddings**.
- Chunks + metadata зберігаються у **Pinecone**.
- Bot дістає релевантний контекст через RAG.

---

# Links

- [Project README](https://github.com/Uhbyxer/supp-bro/blob/main/scripts/final/README.md)
- [Workflow Graph](https://github.com/Uhbyxer/supp-bro/blob/main/scripts/final/README.md#workflow-graph)
- [Як працює RAG](https://github.com/Uhbyxer/supp-bro/blob/main/scripts/final/README.md#%D1%8F%D0%BA-%D1%82%D1%83%D1%82-%D0%BF%D1%80%D0%B0%D1%86%D1%8E%D1%94-rag)
- [Debezium Documentation](https://debezium.io/documentation/reference/stable/)
- [Debezium Issue Tracker](https://github.com/debezium/dbz/issues)
