# ALEMBIC LABS — backend

Autonomous AI laboratory researching performance peptides. Five Claude
agents — Researcher, Literature, Structural, Clinical, Communicator —
collaborate every 45 minutes to generate, validate and publish a fold
hypothesis. Validation is performed in silico via Boltz-2 (and optionally
Chai-1) on Replicate. Each cycle is called a **DISTILLATION** or **FOLD**.

This repository contains the FastAPI HTTP backend powering `alembic.bio`.
The frontend lives in a separate Next.js project (`alembic-labs-frontend`).

> Honest in silico hypothesis generation at scale, in the open.
> Not drug discovery. Not medical advice.

---

## stack

- **Python 3.11+**
- **FastAPI** + **SQLAlchemy 2.0 (async)** + **asyncpg** + **PostgreSQL 15+**
- **Anthropic** (Claude Opus 4.7 + Sonnet 4.6)
- **Replicate** (Boltz-2, Chai-1)
- **httpx** for PubMed / bioRxiv / UniProt / ChEMBL
- **APScheduler** for the 45-minute distillation loop
- **structlog** for structured JSON logs in production
- **pydantic v2** + **pydantic-settings** for config

---

## architecture

```
                ┌───────────────────────────┐
                │   DISTILLATION CYCLE      │
                │   APScheduler · 45 min    │
                └───────────────┬───────────┘
                                │
                                ▼
                          RESEARCHER
                           Opus 4.7
                                │
                  ┌─────────────┴─────────────┐
                  ▼                           ▼
              LITERATURE                  CLINICAL
              Sonnet 4.6                  Sonnet 4.6
              PubMed + bioRxiv            ChEMBL + UniProt
                  │                           │
                  └─────────────┬─────────────┘
                                ▼
                           STRUCTURAL
                       Opus 4.7 + Boltz-2
                       (+ Chai-1 cross-val)
                                │
                                ▼
                          COMMUNICATOR
                          Sonnet 4.6
                          (14-section report)
                                │
                                ▼
              PostgreSQL ──→ FastAPI /api/* ──→ alembic.bio
```

Order can be tuned. Literature and Clinical run in parallel via
`asyncio.gather` because they don't depend on each other after the
Researcher establishes the hypothesis and target.

---

## local setup

Requires Python 3.11+ and a running Postgres 15.

```bash
# 1. Clone + venv
git clone <this-repo> alembic-labs-backend
cd alembic-labs-backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Postgres via Docker
docker run -d --name alembic-pg \
  -e POSTGRES_USER=alembic \
  -e POSTGRES_PASSWORD=alembic \
  -e POSTGRES_DB=alembic_labs \
  -p 5432:5432 \
  postgres:15

# 3. Configure environment
cp .env.example .env
# Fill in:
#   ANTHROPIC_API_KEY=sk-ant-...
#   REPLICATE_API_TOKEN=r8_...
#   BOLTZ2_MODEL_ID=<from https://replicate.com/explore>
#   CHAI1_MODEL_ID=<from https://replicate.com/explore>

# 4. Run
uvicorn alembic_labs.main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/health>
API docs: <http://localhost:8000/api/docs>

### offline / CI mode

For tests or offline development you can run against an in-memory SQLite
without Postgres or any API keys (the scheduler and agent calls won't
actually execute, but the HTTP surface and DB schema work):

```bash
DATABASE_URL='sqlite+aiosqlite:///./alembic_labs.db' \
ENABLE_SCHEDULER=false \
uvicorn alembic_labs.main:app --reload --port 8000
```

---

## env vars

The full list is in `.env.example`. Highlights:

| name | default | purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | required for any agent run |
| `REPLICATE_API_TOKEN` | — | required for the Structural agent |
| `BOLTZ2_MODEL_ID` | — | refresh from `replicate.com/explore` |
| `CHAI1_MODEL_ID` | — | optional, gated by `ENABLE_CHAI1` |
| `DATABASE_URL` | local Postgres | accepts `sqlite+aiosqlite://...` for dev |
| `DISTILLATION_INTERVAL_MINUTES` | `45` | scheduler cadence |
| `ENABLE_SCHEDULER` | `true` | turn off for one-shot cycles in CI |
| `ENABLE_CHAI1` | `true` | toggles Chai-1 cross-validation |
| `CORS_ALLOWED_ORIGINS` | localhost + alembic.bio | comma-separated |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose tracing |
| `APP_ENV` | `development` | `production` switches structlog to JSON |

Each agent's model can be overridden individually via
`RESEARCHER_MODEL`, `LITERATURE_MODEL`, `STRUCTURAL_MODEL`,
`CLINICAL_MODEL`, `COMMUNICATOR_MODEL`.

---

## API

All paths are JSON unless noted. CORS is restricted to the origins listed
in `CORS_ALLOWED_ORIGINS`.

| method | path | description |
| --- | --- | --- |
| GET | `/api/health` | liveness probe |
| GET | `/api/folds` | paginated list. Filters: `peptide_class`, `status`, `sort` (newest/oldest/highest_confidence/lowest_confidence), `page`, `page_size` |
| GET | `/api/folds/{id}` | full 14-section detail |
| GET | `/api/folds/{id}/structure` | PDB text (`chemical/x-pdb`) |
| GET | `/api/folds/{id}/metrics` | plot data (pLDDT per residue, PAE, sequence coverage) |
| GET | `/api/agents/status` | live status for all five agents |
| GET | `/api/stats` | aggregated lab stats for the home page |
| GET | `/api/docs` | Swagger UI |
| GET | `/api/openapi.json` | machine-readable spec |

---

## how a distillation cycle works

1. `Fold` row is created with `status=PENDING`.
2. **Researcher** picks a random KnownPeptide (excluding the last 5 used)
   and asks Claude Opus 4.7 to formulate a concrete modification + target.
3. **Literature** and **Clinical** run in parallel:
   - Literature pulls 8–12 PubMed abstracts and 3–5 bioRxiv preprints,
     then asks Sonnet to synthesise consensus + supporting / challenging
     evidence + knowledge gaps.
   - Clinical pulls ChEMBL bioactivities + UniProt domain annotations and
     asks Sonnet to write a biohacker-context summary.
4. **Structural** resolves the target sequence, submits to Boltz-2 (and
   optionally Chai-1 for cross-validation), saves the PDB to
   `pdb_storage/fold_{id}.pdb`, computes lightweight peptide-property
   heuristics (aggregation, stability, BBB, half-life), and asks Opus
   for the verdict (REFINED / PENDING / DISCARDED).
5. **Communicator** synthesises everything into a 14-section markdown
   report + tweet draft, finalises `Fold.status`, and bumps `LabStat`.
6. The full payload is exposed at `GET /api/folds/{id}`.

A failed Researcher or Structural step aborts the cycle and marks the fold
`FAILED`. Literature, Clinical and Communicator failures are tolerated —
the fold is preserved with whatever data was produced.

---

## cost estimate

Per-cycle (5 agents):

| agent | model | rough cost |
| --- | --- | --- |
| Researcher | Opus 4.7 | $0.10–0.30 |
| Literature | Sonnet 4.6 | $0.05–0.15 |
| Structural | Opus + Boltz-2 | $0.15–0.40 |
| Chai-1 (optional) | Replicate | $0.05–0.15 |
| Clinical | Sonnet 4.6 | $0.05–0.15 |
| Communicator | Sonnet 4.6 | $0.05–0.15 |

**Total: ~$0.45–1.30 per fold**, roughly **$13–65/day** at 30–50 cycles
per day. Tune via `DISTILLATION_INTERVAL_MINUTES` and the `ENABLE_CHAI1`
toggle.

---

## deployment

See `DEPLOY.md` for production VPS setup (Hetzner / DigitalOcean) with
systemd, Nginx, Certbot, log rotation and Postgres backups.

---

## license

MIT.
