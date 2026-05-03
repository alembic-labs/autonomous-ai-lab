# Alembic prod stack (Docker)

Поднимает на **одной машине**:

- **PostgreSQL 15**
- **FastAPI** бэкенд (порт внутри сети `8000`)
- **Next.js** фронт (`3000`)
- **3D lab** как статика через **nginx** (`80`)
- **Caddy** снаружи: `80/443` → TLS (Let’s Encrypt) и маршруты:
  - `https://alembic.bio` → фронт  
  - `https://api.alembic.bio` → API  
  - `https://lab.alembic.bio` → 3D  

## DNS

У регистратора для `alembic.bio` поставь **A-записи** на IP VPS `178.18.240.104`:

| Имя | Тип | Значение |
|-----|-----|---------|
| `@` | A | `178.18.240.104` |
| `api` | A | `178.18.240.104` |
| `lab` | A | `178.18.240.104` |
| `www` | A | `178.18.240.104` (редирект на корень в Caddy) |

Пока DNS не укажет на сервер, сертификаты Let’s Encrypt могут не выпуститься — это нормально, подожди пропагации.

## На VPS

1. Установи Docker + Compose (пример для Ubuntu/Debian):

   ```bash
   curl -fsSL https://get.docker.com | sh
   ```

2. Скопируй **весь репозиторий** на сервер, например в `/opt/alembic` (можно через `scp -r`, `rsync`, или `git clone`).

3. Перейди в папку `deploy` репозитория на сервере:

   ```bash
   cd /opt/alembic/deploy   # поправь путь, если у тебя другой
   ```

4. Положи сюда файл **`.env`** (скопируй с макбука из этого же каталога `deploy/.env`, или собери из `deploy/.env.example`).

5. Собери и запусти:

   ```bash
   docker compose up -d --build
   ```

6. Логи:

   ```bash
   docker compose logs -f
   ```

Проверки:

- `https://api.alembic.bio/api/health`
- `https://alembic.bio`

## Локально на макбуке (без VPS)

Из корня репозитория:

```bash
cd deploy
docker compose up -d --build
```

Тот же `deploy/.env` — URL в нём уже на боевые поддомены; для локальной проверки поменяй `NEXT_PUBLIC_*` и при необходимости `CORS_*` на `http://localhost:3000` и временно другой compose.

## Секреты

Файл `deploy/.env` в `.gitignore` — **не коммить**. После любой утечки ротируй `ANTHROPIC_API_KEY` и `BIOLMAI_TOKEN` и обнови `.env`.

## SSH

Подключаться лучше **ключом**, без пароля root. Из этой среды доступ по паролю к твоему VPS недоступен — деплой делаешь ты с машины командой выше после копирования файлов.
