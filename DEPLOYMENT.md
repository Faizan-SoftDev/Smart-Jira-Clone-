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
