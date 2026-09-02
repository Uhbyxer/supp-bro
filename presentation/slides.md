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

**Customer Team → Support → ? → Product Team**

`? = Bug / Configuration / Known Limitation / Ownership`
