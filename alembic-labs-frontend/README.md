# ALEMBIC LABS — frontend

Autonomous AI laboratory for performance peptides. Public site at
[alembic.bio](https://alembic.bio). Backend lives in a separate Cursor project
(see `CURSOR_PACK.md` at the repo root).

## stack

- Next.js 14 (App Router) + TypeScript (strict)
- Tailwind CSS, custom theme — JetBrains Mono only, plasma red accent
- 3Dmol.js (3D molecular viewer)
- Recharts (pLDDT / PAE plots)
- @anthropic-ai/sdk (Stack Analyzer streaming via Next.js API route)
- react-markdown, lucide-react

## local setup

```bash
cp .env.example .env.local
# fill ANTHROPIC_API_KEY for the Stack Analyzer
# point NEXT_PUBLIC_API_URL at the backend (default: http://localhost:8000)

npm install
npm run dev
```

Open `http://localhost:3000`.

## env vars

| name | scope | description |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | client + server | backend base URL, no trailing slash |
| `ANTHROPIC_API_KEY` | server-only | used by `/api/stack` SSE route |
| `STACK_MODEL_ID` | server-only | model used by Stack Analyzer (default `claude-opus-4-7`) |

## scripts

- `npm run dev` — dev server with hot reload
- `npm run build` — production build
- `npm run start` — production server
- `npm run lint` — ESLint
- `npm run type-check` — TypeScript without emit

## deployment

- Vercel — connect repo, set env vars, attach `alembic.bio` domain.
- CORS on the backend must allow the frontend origin.

## project structure

See `CURSOR_PACK_FRONTEND.md` §4 at the repo root for the full layout.
