# AkashiMedia — Архитектурный контракт

## Стек
Python 3.12 · FastAPI · htmx + Jinja2 · OpenAI API · pytest

## Гексагональная архитектура — ЖЁСТКИЕ правила
- `src/domain/` — чистое ядро. НЕ импортирует ничего из `adapters/`, `entrypoints/`, никаких внешних SDK.
- Порты — это `typing.Protocol` в `src/domain/ports/`.
- Адаптеры реализуют порты, живут в `src/adapters/`.
- Связывание всего — только в `src/config.py` (composition root).
- Зависимости направлены ВНУТРЬ: entrypoints → application → domain. Обратно — запрещено.

## Паттерны и где они
- Strategy: PublisherPort, ContentAdapterPort
- Factory: PublisherFactory (выбор канала по строке)
- Command: один use-case = один класс в application/commands/
- Repository: PostRepository (сейчас in-memory, БД — Фаза 2)

## Scope Cut Фазы 1 (НЕ делать)
Отложенный постинг, БД истории, аналитика, сложная авторизация. Только единый логин.

## Секреты
Только через os.environ. .env в .gitignore. Ключи: OPENAI_API_KEY, IG_TOKEN, LI_TOKEN.
