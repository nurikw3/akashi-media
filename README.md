# AkashiMedia — Фаза 1 (MVP)

Транзитный шлюз для SMM: загрузить фото и текст → опубликовать в Instagram →
переупаковать текст под деловой тон LinkedIn через ИИ → проверить/отредактировать
→ опубликовать в LinkedIn. История не хранится, отложенного постинга нет
(см. Scope Cut в [CLAUDE.md](CLAUDE.md)).

## Стек

Python 3.12 · FastAPI · htmx + Jinja2 · OpenAI API · pytest. Гексагональная
архитектура (домен не зависит от адаптеров; порты — `typing.Protocol`; связывание
только в `src/config.py`).

## Структура

```
src/
├── domain/            # чистое ядро: models, errors, ports/ (Protocol)
├── application/       # commands/ — по одному use-case на класс
├── adapters/          # publishers/ (IG, LinkedIn, fake), content/ (OpenAI, fake), repositories/
├── config.py          # composition root — единственное место связывания
└── entrypoints/web/   # FastAPI app, auth, routes, templates, static
```

## Запуск

Используется [uv](https://docs.astral.sh/uv/) (Python 3.12 закреплён в `.python-version`):

```bash
uv sync                     # создаёт .venv и ставит зависимости (вкл. dev)
cp .env.example .env        # заполнить APP_USERNAME/APP_PASSWORD/APP_SECRET_KEY (>=32)
uv run python -m src.entrypoints.web.server   # http://127.0.0.1:8000
```

Без `OPENAI_API_KEY` / `IG_TOKEN` / `LI_TOKEN` приложение работает на
**fake-адаптерах** — весь поток проходит end-to-end без обращения к внешним API.
Реальные адаптеры подключаются автоматически, как только заданы ключи.

### Переменные окружения

| Переменная | Назначение |
|---|---|
| `APP_USERNAME` / `APP_PASSWORD` | единый логин отдела маркетинга |
| `APP_SECRET_KEY` | подпись сессионной cookie (≥ 32 символа) |
| `APP_HTTPS_ONLY` | `true` за TLS — флаг Secure на cookie |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | переупаковка текста (LinkedIn) |
| `IG_TOKEN` / `IG_USER_ID` | публикация в Instagram (Graph API) |
| `LI_TOKEN` / `LI_AUTHOR_URN` | публикация в LinkedIn (Posts API) |

> Instagram Graph API требует **публичный URL** изображения (не принимает байты).
> Хостинг медиа — Фаза 2; до тех пор реальная IG-публикация возвращает понятную
> ошибку, а fake-адаптер проверяет поток.

## Тесты

```bash
uv run pytest                   # юнит + интеграционные (live пропускаются без ключей)
uv run pytest -m live           # реальные вызовы API (нужны токены, см. tests/integration/)
```

Покрытие ~93%. Живые тесты публикации помечены `@pytest.mark.live` и
пропускаются, пока не заданы соответствующие токены.
