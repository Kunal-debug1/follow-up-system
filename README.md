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

Requirements: Python 3.11+, Node.js, and a local PostgreSQL database.

Set the backend environment variables in your terminal. These are examples for PowerShell; use the equivalent `export NAME=value` syntax in Bash. Never use production secrets for local development.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/crm"
$env:CRM_ADMIN_USERNAME = "admin"
$env:CRM_ADMIN_PASSWORD = "change-this-local-password"
$env:CRM_AUTH_SECRET = "replace-with-a-long-random-local-secret"
$env:CORS_ORIGINS = "http://localhost:5173"
```

Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal, install and start the frontend:

```powershell
cd frontend
npm ci
$env:VITE_API_URL = "http://127.0.0.1:8000"
npm run dev
```

The API's interactive documentation is available at `/docs`; liveness and database readiness are available at `/health` and `/health/ready`. The required and optional environment variable names are listed in [`.env.example`](.env.example); the app reads them from the process environment.

## Configuration

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

Backend tests and a frontend production build are included in the repository. Run the project's configured checks before submitting changes.

## Project status

This is an actively developed portfolio project. Review the code and deployment configuration before using it with real customer data; it is not presented as a certified or compliance-reviewed CRM.
