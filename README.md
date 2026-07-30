# Smart Jira Clone

Run all commands from this repository root. Do not run the duplicate `smart-pm-tool/` folder.

## Docker

```bash
docker compose up --build
```

Open the frontend at `http://localhost:5173` and API documentation at `http://localhost:8000/docs`.

Seed local validation accounts and project templates after the stack is up:

```bash
docker compose exec backend python seed_data.py
```

The seed is idempotent. Override the local-only default passwords with
`SEED_ADMIN_PASSWORD`, `SEED_MANAGER_PASSWORD`, and `SEED_DEVELOPER_PASSWORD`
before running it.

Run the verification suite with `pip install -r backend/requirements-dev.txt`
followed by `PYTHONPATH=backend python -m pytest`.

Stop the stack with `Ctrl+C`, then run `docker compose down`.

## Local development

Start PostgreSQL first:

```bash
docker compose up database -d
```

Terminal 1:

```bash
source .venv/bin/activate
export DATABASE_URL='postgresql+psycopg://smart_jira:change-this-local-password@localhost:5432/smart_jira'
export CREATE_DATABASE_SCHEMA=true
uvicorn --app-dir backend app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in the browser. The API health endpoint is `http://localhost:8000/health`.

## Production deployment

Deploy the frontend to Vercel and the API, PostgreSQL, and Redis services to
Render using the instructions in [DEPLOYMENT.md](DEPLOYMENT.md).
