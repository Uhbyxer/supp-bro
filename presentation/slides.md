---
marp: true
theme: default
paginate: true
---

# Проблема

### Контекст

- **Product teams** мають глибокі знання про свої features.
- **Support team** знає загальний продукт, але не всі implementation details.
- **Customer teams** впроваджують продукт для конкретних клієнтів.

### Проблема

- Customer team відкриває issue, але причина часто неочевидна.
- Незрозуміло: це **bug**, **configuration issue** чи **known limitation**.
- Якщо це bug — незрозуміло, **яка product team повинна його розбирати**.
- Support витрачає час на пошук документації, старих issues та схожих кейсів.
- Product teams отримують багато запитів, які можна було б відфільтрувати раніше.

### Ключова теза

> Support потрібен швидкий спосіб зібрати релевантний контекст і зрозуміти, куди правильно маршрутизувати проблему.

---

# Де виникає bottleneck

![width:1050px](assets/team-routing.svg)

> Кілька customer teams сходяться в одну support team, яка має визначити причину проблеми та правильну product team.

---

# Ідея: POC Support Bot

- Допомагає Support team швидко увійти в **контекст проблеми**.
- Розуміє, **які features зараз розробляються**.
- Знає, **яка Product team / engineer відповідає за feature**.
- Робить первинний **triage issue**.
- Перевіряє, чи **схожа проблема вже була в іншого клієнта**.
- Визначає: **bug / configuration issue / known limitation / already known issue**.
- Підказує, чи проблему можна вирішити **зміною конфігурації без залучення Product team**.
- Збирає релевантний контекст із **documentation, GitHub issues та інших джерел**.

> Support Bot не замінює Product team — він допомагає Support швидше зрозуміти проблему і правильно її маршрутизувати.
