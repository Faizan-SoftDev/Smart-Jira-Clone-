# Production deployment: Vercel + Render

The API, Postgres database, and Redis backplane deploy to Render from
`render.yaml`. The React/Vite application deploys separately to Vercel.

## 1. Prepare the repository

Push this repository to a private GitHub repository. Do not commit `.env` or
any real API, database, or JWT secrets.

## 2. Deploy the API on Render

1. In Render, select **New > Blueprint** and connect the GitHub repository.
2. Render reads `render.yaml` and provisions `smart-jira-api`, Postgres, and
   the private Redis-compatible Key Value service.
3. During setup, set `OPENAI_API_KEY` only if AI task analysis is required.
4. After the API has its public URL, set `CORS_ORIGINS` to the exact Vercel
   production URL, for example `https://smart-jira.vercel.app`. Add preview
   URLs as comma-separated values if you use them.
5. Confirm `https://<your-render-api>/health` returns `{"status":"ok"}`.
6. Seed the initial users and project templates from the Render Shell:

   ```bash
   python seed_data.py
   ```

Render keeps `OPENAI_API_KEY` and `CORS_ORIGINS` out of source control. Its
Blueprint also generates `JWT_SECRET` on initial provisioning.

## 3. Deploy the frontend on Vercel

1. Import the same GitHub repository into Vercel. Keep the project root at
   the repository root so Vercel uses `vercel.json`.
2. Add these Production environment variables, substituting your Render URL:

   ```text
   VITE_API_BASE_URL=https://<your-render-api>/api/v1
   VITE_KANBAN_WS_URL=wss://<your-render-api>/ws/kanban
   ```

3. Deploy. Vite embeds `VITE_*` variables during the build, so redeploy after
   changing either value.
4. Copy the resulting Vercel URL into Render's `CORS_ORIGINS`, then redeploy
   the API once.

## Production checks

- Sign in with a seeded account and create a task in a project.
- Open two browser windows and move a task; the second board should update.
- Verify a Developer account receives `403` from `analyze-ai` while an Admin
  or Project Manager can use it.
# Production proxy baseline

Use `deploy/nginx/taskcraft.conf` as the reverse-proxy baseline. Terminate TLS
at Nginx or Cloudflare, set production secrets, and route `/ws/` with Upgrade
headers so authenticated project-board sockets remain connected.

Build the frontend, then start the production-shaped compose stack:

```bash
cd frontend && npm ci && npm run build
cd ..
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Before running this command, set `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`,
`DJANGO_ALLOWED_HOSTS`, PostgreSQL credentials, Redis URL, Stripe keys, and a
production Sentry DSN in the deployment environment.
