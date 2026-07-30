# Smart Jira Clone

An AI-powered, real-time project management platform built with FastAPI,
PostgreSQL, Redis, React, TypeScript, and Docker Compose.

## Local development

Run the application stack:

```bash
docker compose up --build -d
```

Open the frontend at `http://localhost:5173`, API docs at
`http://localhost:8000/docs`, and the health endpoint at
`http://localhost:8000/health`.

Seed the initial Admin, Project Manager, Developer, and project templates:

```bash
docker compose exec backend python seed_data.py
```

Install test dependencies and run the suite locally:

```bash
pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python -m pytest
```

## Production deployment

The repository includes a Vercel + Render deployment configuration:

- `render.yaml` provisions the FastAPI API, Render Postgres, and private Redis.
- `vercel.json` builds the React/Vite frontend.

Follow [DEPLOYMENT.md](DEPLOYMENT.md) to configure the public API URL, Vercel
environment variables, CORS origins, secrets, and the first production seed.
