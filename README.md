# AkashiMedia — Фаза 1 (MVP)

Транзитный шлюз для SMM: загрузить фото и текст → опубликовать в Instagram →
переупаковать текст под деловой тон LinkedIn через ИИ → проверить/отредактировать
→ опубликовать в LinkedIn. Отдельный Telegram-бот умеет по команде `1` найти
свежие новости отрасли дата-центров и опубликовать два индивидуальных поста.
Для IT-дайджеста хранится история в PostgreSQL: это исключает повторные
публикации и даёт статистику на вкладке «Дайджест».

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
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint; для `openai/gpt-oss-120b` по умолчанию Groq |
| `IG_TOKEN` / `IG_USER_ID` | публикация в Instagram (Graph API) |
| `LI_TOKEN` / `LI_AUTHOR_URN` | публикация в LinkedIn (Posts API) |
| `BUFFER_API_KEY` / `BUFFER_LINKEDIN_CHANNEL_ID` | при наличии имеют приоритет для LinkedIn: текст ставится в очередь подключённого канала Buffer |
| `TELEGRAM_BOT_TOKEN` | токен Telegram-бота от BotFather |
| `TELEGRAM_CHANNEL_ID` | целевой канал (`-100...` или `@username`) |
| `TELEGRAM_CONTROL_CHAT_ID` | единственный личный чат, где команда `1` разрешена |
| `TAVILY_API_KEY` | поиск свежих материалов Equinix и Data Center Dynamics |
| `DIGEST_POST_LIMIT` | число отраслевых постов за запуск, по умолчанию `2`; затем добавляется один свежий материал Equinix Blog |

> Instagram Graph API требует **публичный URL** изображения (не принимает байты).
> Хостинг медиа — Фаза 2; до тех пор реальная IG-публикация возвращает понятную
> ошибку, а fake-адаптер проверяет поток.

## Telegram IT-дайджест дата-центров

Бот работает отдельным процессом на `aiogram` long polling и не требует cron.
Ключи из локального `keys.txt` нужно перенести в `.env` под именами из
`.env.example`; сам файл игнорируется Git и приложением не читается. Для
локального Docker PoC его может безопасно прочитать только wrapper
`scripts/compose.py` (значения не печатаются).

Соответствие предоставленных имён:

| `keys.txt` | `.env` |
|---|---|
| `bot_id` | `TELEGRAM_BOT_TOKEN` (нужен именно токен, не числовой id) |
| `telegram_channel_id` | `TELEGRAM_CHANNEL_ID` |
| `tavily_api` | `TAVILY_API_KEY` |
| `openai` | `OPENAI_API_KEY` |

Первый запуск нужен для определения управляющего chat ID:

```bash
uv run python -m src.entrypoints.telegram.bot
```

1. Напишите боту `/start`.
2. Скопируйте показанный id в `TELEGRAM_CONTROL_CHAT_ID` в `.env`.
3. Перезапустите процесс и отправьте `1`.

Бот ищет свежие материалы за месяц в отраслевых источниках, удаляет дубликаты
по URL/заголовку и создаёт моделью `openai/gpt-oss-120b` отдельный
русскоязычный пост для каждого источника. После `DIGEST_POST_LIMIT` отраслевых
новостей он автоматически добавляет ещё один пост по самой свежей релевантной
статье из Equinix Blog. Посты содержат источник, дату публикации исходной
статьи и ссылку.
Ссылка на оригинал всегда добавляется приложением. Ручной запуск публикует
свежие уникальные материалы сразу; PostgreSQL хранит URL, результат и время
публикации. Вкладка **«Дайджест»** показывает число публикаций, число за
сегодня и последние материалы.

### Docker Compose: сайт, бот, worker и PostgreSQL

Docker Compose поднимает четыре процесса: сайт на `http://localhost:8000`,
PostgreSQL, long-polling Telegram-бот и отдельный worker. Миграция выполняется
один раз до старта сервисов. Worker сразу создаёт базу уже найденных статей
без публикации, а затем делает проверку каждые 4 часа; последующие
публикуют только новые URL.

Заполните `.env`, затем передайте секреты из `keys.txt` в переменные окружения
с теми же именами, что указаны в таблице выше, и запустите:

```bash
docker compose up --build -d
docker compose ps
```

Для локального PoC можно использовать `keys.txt` (он игнорируется Git):

```bash
uv run python scripts/compose.py up --build -d
uv run python scripts/compose.py ps
```

Для любого общего/production-окружения заполните `.env` и используйте обычный
`docker compose`; wrapper читает `keys.txt` только локально и не выводит ключи.

Для просмотра состояния: `docker compose logs -f web telegram-bot digest-worker`.
Остановить стек: `docker compose down`. Данные истории сохраняются в volume
`postgres_data`; для полного удаления данных используйте `docker compose down -v`.

## Тесты

```bash
uv run pytest                   # юнит + интеграционные (live пропускаются без ключей)
uv run pytest -m live           # реальные вызовы API (нужны токены, см. tests/integration/)
```

Покрытие ~93%. Живые тесты публикации помечены `@pytest.mark.live` и
пропускаются, пока не заданы соответствующие токены.
