# TripGraph AI

Multi-agent travel planner. A supervisor agent splits the request across flight, hotel, weather, research and budget agents, an itinerary agent drafts the plan, and a human approval step can send it back for revision before the final answer.

- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, streamed chat, itinerary and map views
- **Backend**: FastAPI, LangGraph, MCP weather server mounted in-process, Tavily and OpenWeather tools, Postgres or in-memory checkpoints
- **LLM gateway**: ordered fallback across OpenAI, Anthropic, Groq and Gemini

## Repository layout

```
TripGraph-AI/
├── backend/             FastAPI service (deployed to Render)
│   ├── app/
│   │   ├── graph.py     supervisor and agent graph
│   │   ├── llm/         multi-provider router with fallback
│   │   ├── service.py   run, stream and approval orchestration
│   │   └── tools/       MCP weather client and server
│   └── tests/
├── frontend/            Next.js app (deployed to Vercel)
├── documentation/       architecture diagram
├── docker-compose.yml   API + web + Postgres stack for local Docker runs
└── render.yaml          Render blueprint
```

## Running with Docker

Requirements: Docker only.

```bash
cp .env.example .env   # add at least one LLM key, plus Tavily and OpenWeather for full function
docker compose up --build
```

- Web app: http://localhost:3000
- API: http://localhost:8000, `/health` reports provider and MCP status

Notes:

- `docker-compose.yml` builds `backend/Dockerfile` (Python 3.12 slim, non-root, `HEALTHCHECK` on `/health`) and `frontend/Dockerfile` (Next.js standalone output on Node 22 alpine), and starts a `postgres:17-alpine` service for durable conversation state.
- The API waits for Postgres to pass `pg_isready`, and the web container waits for the API to report healthy.
- `DATABASE_URL` defaults to the bundled Postgres. It is optional: to fall back to the in-memory checkpointer, clear `DATABASE_URL` and delete the `DATABASE_URL` line from the `api` service in `docker-compose.yml`. To use an external database, set `DATABASE_URL` in `.env`; note that changing the `POSTGRES_*` variables also means updating `DATABASE_URL` in the compose file, and that the bundled Postgres is plaintext, which is why its default URL carries `sslmode=disable`.
- `NEXT_PUBLIC_API_URL` is compiled into the browser bundle at build time and defaults to `http://localhost:8000`. Set it before `docker compose up` if the API lives somewhere else.

`.github/workflows/docker.yml` builds both images on every push and pull request so Dockerfile changes cannot rot unnoticed.

## Running locally

Requirements: Python 3.12+, Node.js 20+.

1. Copy `.env.example` to `.env` in the repository root and fill in the keys.
2. Start the API:

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate            # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

3. Start the web app:

   ```bash
   cd frontend
   cp .env.example .env.local
   npm install
   npm run dev
   ```

Open http://localhost:3000.

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

```bash
cd frontend
npm test
npm run typecheck
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/travel` | Plan a trip, single JSON response |
| `POST` | `/api/travel/approve` | Approve or request a revision of a draft |
| `POST` | `/api/chat/stream` | Streamed plan as Server-Sent Events |
| `POST` | `/api/chat/approve/stream` | Streamed approval or revision |
| `GET` | `/api/threads/{thread_id}` | Result of a finished conversation |
| `GET` | `/health` | Liveness probe with checkpointer and MCP status |

## Configuration

All settings are environment variables, listed in [.env.example](.env.example). Only providers with a key set are used, so the app runs with any subset of OpenAI, Anthropic, Groq and Gemini. `DATABASE_URL` is optional, `ALLOWED_ORIGINS` and `ALLOWED_ORIGIN_REGEX` control browser access.

## Deployment

- Backend: Render web service from `render.yaml` (root directory `backend`).
- Frontend: Vercel project with root directory `frontend` and `NEXT_PUBLIC_API_URL` pointing at the Render URL.