#!/usr/bin/env bash
# Локальный запуск БЕЗ Docker: бэкенд + фронт одной командой.
# Нужно только: Python 3.11+ и Node.js (npm) — обычно уже стоят, если ты в Cursor крутишь проект.
#
# Использование (из корня репозитория):
#   chmod +x run-local.sh
#   ./run-local.sh
#
# Требуется deploy/.env с ANTHROPIC_API_KEY, BIOLMAI_TOKEN и т.д. (как для прода).
# База: SQLite в alembic-labs-backend/alembic_labs_local.db — Postgres не нужен.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/deploy/.env"
BE="$ROOT/alembic-labs-backend"
FE="$ROOT/alembic-labs-frontend"

die() { echo "$*" >&2; exit 1; }

command -v python3 >/dev/null || die "Нет python3. Поставь Python 3.11+ (brew install python@3.11) или с официального сайта."
command -v node >/dev/null || die "Нет node. Поставь Node LTS (nodejs.org или brew install node)."
command -v npm >/dev/null || die "Нет npm — положи Node LTS."

[[ -f "$ENV_FILE" ]] || die "Нет $ENV_FILE — скопируй deploy/.env.example → deploy/.env и впиши ключи."

# Подтянуть секреты из .env (формат KEY=value, без странных переносов)
set -a
# shellcheck disable=1090
source "$ENV_FILE"
set +a

# Локально без Docker: SQLite + CORS под Next dev
export DATABASE_URL="sqlite+aiosqlite:///${BE}/alembic_labs_local.db"
export CORS_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
export PDB_STORAGE_DIR="${BE}/pdb_storage_local"
mkdir -p "$PDB_STORAGE_DIR"

export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
export NEXT_PUBLIC_LAB_3D_URL=""

if [[ ! -d "$BE/.venv" ]]; then
  echo "→ создаю venv в alembic-labs-backend/.venv …"
  python3 -m venv "$BE/.venv"
fi
# shellcheck disable=1091
source "$BE/.venv/bin/activate"

STAMP="$BE/.venv/.deps_installed"
if [[ ! -f "$STAMP" ]]; then
  echo "→ pip install (первый раз дольше) …"
  pip install -q -r "$BE/requirements.txt"
  touch "$STAMP"
fi

cleanup() {
  if [[ -n "${BACK_PID:-}" ]] && kill -0 "$BACK_PID" 2>/dev/null; then
    kill "$BACK_PID" 2>/dev/null || true
    wait "$BACK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "→ бэкенд http://127.0.0.1:8000 …"
(cd "$BE" && uvicorn alembic_labs.main:app --host 127.0.0.1 --port 8000) &
BACK_PID=$!

echo "→ жду /api/health …"
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
    echo "→ API живой."
    break
  fi
  sleep 0.5
done
curl -sf "http://127.0.0.1:8000/api/health" >/dev/null || die "Бэкенд не поднялся — см. ошибки выше."

if [[ ! -d "$FE/node_modules" ]]; then
  echo "→ npm install во фронте (первый раз) …"
  (cd "$FE" && npm install)
fi

echo "→ фронт http://localhost:3000 (Ctrl+C — всё выключится)"
(cd "$FE" && npm run dev)
