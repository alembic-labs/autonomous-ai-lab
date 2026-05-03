# Проверка лаборатории на компе (без доменов, без 3D)

## Вариант А — без Docker (одна команда)

Из **корня репозитория**:

```bash
chmod +x run-local.sh
./run-local.sh
```

Нужно только **Python 3.11+** и **Node.js** (обычно уже есть, если проект открыт в Cursor).

Скрипт сам:
- читает ключи из **`deploy/.env`**;
- поднимает бэкенд на **http://127.0.0.1:8000** (база **SQLite** в `alembic-labs-backend/alembic_labs_local.db`, Postgres не нужен);
- поднимает фронт на **http://localhost:3000**.

Остановка: **Ctrl+C** в этом терминале.

| Что | URL |
|-----|-----|
| Сайт (чат Stack, фолды) | http://localhost:3000 |
| API | http://127.0.0.1:8000/api/health |
| Фолды | http://127.0.0.1:8000/api/folds |
| Доки | http://127.0.0.1:8000/api/docs |

В `deploy/.env` нужны хотя бы **`ANTHROPIC_API_KEY`** и **`BIOLMAI_TOKEN`** (остальное можно как в примере). Строку `DATABASE_URL` для этого режима можно не трогать — скрипт всё равно переключает на SQLite на время `./run-local.sh`.

---

## Вариант B — через Docker (+ Postgres как на сервере)

Нужны **Docker Desktop** (или двигатель Compose).

Из папки `deploy`:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

Там же **Postgres**, URL и CORS уже под localhost. Логи бэкенда:

```bash
docker compose -f docker-compose.local.yml logs -f backend
```

Подробнее про интервал цикла / отключение планировщика — см. раздел ниже.

---

## Цикл агентов (оба варианта)

При **`ENABLE_SCHEDULER=true`** планировщик периодически гоняет полный конвейер (дорого по Anthropic + BioLM). Чтобы **`не ждать 45 минут`**, временно в `deploy/.env`: `DISTILLATION_INTERVAL_MINUTES=3`.

Только сайт и чат, без автоматических циклов: **`ENABLE_SCHEDULER=false`**.

## Чат Stack

Чат дергает **`/api/stack`** у Next-сервера; нужен **`ANTHROPIC_API_KEY`** в `deploy/.env` (скрипт `run-local.sh` подставляет переменные из этого файла и для фронта тоже).
