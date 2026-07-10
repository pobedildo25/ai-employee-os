# Architecture Decision Records (ADR)

Этот каталог содержит Architecture Decision Records — документы, фиксирующие значимые архитектурные решения проекта AI Employee OS.

## Что такое ADR

ADR — короткий документ, описывающий:
- **Контекст** — какая проблема или вопрос стоит
- **Решение** — что было выбрано
- **Последствия** — плюсы, минусы, trade-offs

## Формат

Каждый ADR — отдельный файл:

```
ADR/
├── README.md          ← этот файл
├── 0001-langgraph-as-runtime.md
├── 0002-llm-gateway.md
└── ...
```

### Шаблон

```markdown
# ADR-NNNN: Название решения

## Status

Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

## Context

Какая проблема или вопрос?

## Decision

Что решили?

## Consequences

### Positive
- ...

### Negative
- ...

### Neutral
- ...
```

## Нумерация

- `0001` — первое решение
- Номера последовательные, без пропусков
- Superseded ADR не удаляются — помечаются статусом

## Когда создавать ADR

- Выбор технологии (LangGraph, Qdrant, Mem0)
- Архитектурный паттерн (Skill Registry, LLM Gateway)
- Изменение подхода к памяти или документам
- Отказ от альтернативы с обоснованием

## Планируемые ADR

| # | Тема | Статус |
|---|------|--------|
| 0001 | LangGraph как agent runtime | Planned |
| 0002 | LLM Gateway вместо прямых вызовов OpenRouter | Planned |
| 0003 | Skill Registry как расширяемая модель | Planned |
| 0004 | Многоуровневая архитектура памяти | Planned |
| 0005 | Document AST для document intelligence | Planned |
| 0006 | Human Approval Layer для сложных задач | Planned |

## Связанные документы

- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md)
