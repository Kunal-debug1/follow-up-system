# CRM Follow-Up System

A full-stack CRM for managing customers, call history, and scheduled follow-ups. It pairs a React dashboard with a FastAPI API and PostgreSQL database.

## Highlights

- Customer search and record management
- Excel/CSV import with validation, duplicate checks, and configurable upload/row limits
- Call history and follow-up scheduling with Today, Upcoming, and Overdue views
- Admin login with HMAC-signed, time-limited session tokens
- SQLAlchemy models and Alembic migrations
- Health and database readiness endpoints
- Separate frontend and API deployments described in `render.yaml`

## Stack

- **API:** Python, FastAPI, SQLAlchemy, Pydantic, psycopg, Alembic
- **Frontend:** React, Vite, JavaScript, Lucide
- **Database:** PostgreSQL (including Supabase PostgreSQL)
- **Hosting configuration:** Render

## Architecture

```
React + Vite ──HTTP──> FastAPI ──SQLAlchemy──> PostgreSQL
                           ├── customers
                           ├── follow-ups
                           └── spreadsheet imports
```

## Run locally

Requirements: Python 3.11+ and Node.js.

1. Create a local PostgreSQL database.
2. Create a root `.env` from `.env.example` and fill in the values. Use a local database URL, local frontend origin in `CORS_ORIGINS`, and development-only admin credentials and auth secret. Do not use production secrets locally or commit `.env`.
3. Start the backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

4. In another terminal, install and start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Set `VITE_API_URL` to the local API URL if it differs from the frontend's configured default. The API's interactive documentation is available at `/docs`; liveness and database readiness are available at `/health` and `/health/ready`.

## Configuration

The application reads configuration from environment variables. See [`.env.example`](.env.example) for the full list.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URI |
| `CRM_ADMIN_USERNAME` / `CRM_ADMIN_PASSWORD` | Admin login |
| `CRM_AUTH_SECRET` | Signs session tokens |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `VITE_API_URL` | Frontend API base URL |
| `IMPORT_BATCH_SIZE`, `MAX_UPLOAD_BYTES`, `MAX_WORKSHEET_ROWS` | Optional spreadsheet import limits |
| `BACKEND_HEALTH_URL` | Health URL used by the optional Render keepalive cron |

Keep credentials and database URLs private. Use a dedicated, least-privilege database account for deployments.

## Deployment

The included [`render.yaml`](render.yaml) describes a FastAPI web service, a static frontend, and an optional keepalive cron service. Configure the required environment variables in Render. The API runs Alembic migrations before deployment and exposes `/health` as its liveness check.

## Repository layout

```
backend/
  app/
    core/       configuration
    routers/    customer, follow-up, and import endpoints
    services/   application services
    database.py SQLAlchemy engine and sessions
  migrations/   Alembic migrations
  requirements.txt
frontend/
  src/          React application
  package.json
render.yaml
.env.example
```

## Testing

Backend tests and a frontend production build are part of the project workflow. Run the commands documented in the repository's test configuration before submitting changes.

## Project status

This is an actively developed portfolio project. Review the code and deployment configuration before using it with real customer data; it is not presented as a certified or compliance-reviewed CRM.
