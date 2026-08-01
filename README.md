# TaskCraft

TaskCraft is a multi-tenant work-management platform, built with Django,
Django REST Framework, Channels, Celery, PostgreSQL, and Redis.

## Step 1: local foundation

The repository is already a Git repository. Python 3.14.4 is used locally;
the production container uses Python 3.13, satisfying the Python 3.13+
baseline. The virtual environment lives at `.venv` and is intentionally
excluded from Git.

```bash
# Activate the existing virtual environment.
source .venv/bin/activate

# Install runtime and test dependencies.
python -m pip install -r backend/requirements-dev.txt

# Copy the safe configuration template before adding local secrets.
cp .env.example .env

# Validate Django's configuration and start the development server.
python backend/manage.py check
python backend/manage.py runserver
```

The first local run uses SQLite when `DATABASE_URL` is absent. Use Docker for
the production-like PostgreSQL and Redis services:

```bash
docker compose up --build
```

Visit `http://localhost:8000/health/` to confirm the service is running.

## Initial architecture

`backend/config/` contains environment-specific settings plus ASGI/WSGI entry
points. `backend/apps/` keeps domain boundaries explicit: `accounts`,
`workspaces`, `projects`, and `issues`. The `core` app is reserved for small,
shared primitives rather than business rules. Each business app will evolve
with `models`, `services`, `api`, and `tests` modules, keeping views thin and
tenant-sensitive logic in services.

Development uses Django's in-memory Channels layer so the project is usable
without Redis. Production swaps this for scoped Redis channels. Celery is
configured around the same Redis URL, but workers will be introduced when the
first background job exists.

## Step 2: identity, tenancy, and roles

The project uses a custom email-based `User` model from its first migration.
This must happen before any production migrations, because replacing Django's
default user model afterwards is expensive and error-prone.

`Workspace` is the tenant boundary. Every future project, issue, attachment,
and report must reference one workspace. `WorkspaceMembership` stores exactly
one role per user/workspace pair. The database enforces that invariant and
indexes the two access paths used by authorization checks.

Create a superuser for the local admin interface:

```bash
source .venv/bin/activate
python backend/manage.py migrate
python backend/manage.py createsuperuser
```

To validate this milestone:

```bash
python backend/manage.py check
python backend/manage.py test apps.accounts apps.workspaces -v 2
```

## Step 3: teams and projects

Teams and projects are both tenant-scoped. A project key (`TC`, `PAY`, etc.)
and slug only need to be unique within its workspace, which makes imports and
human-friendly URLs predictable without creating global naming collisions.

`ProjectSettings` is created with every project and holds the deliberately
small configuration surface needed before issue workflows are introduced. A
project lead and every project member refer to an existing workspace
membership; service-layer validation rejects references from another tenant.

```bash
source .venv/bin/activate
python backend/manage.py migrate
python backend/manage.py test apps.accounts apps.workspaces apps.projects -v 2
```

The service functions in `apps.projects.services` are the approved write path
for these aggregates. They create projects, their lead membership, and their
settings in one transaction.

## Step 4: workflows and issues

Issues belong to one project and receive an immutable, sequential key such as
`TC-42`. Their types are Epic, Story, Task, Bug, and Sub-task. A project gets
a safe default workflow on first issue creation: To Do → In Progress → Done,
plus explicit back and reopen transitions. Later workflow customization will
extend these records rather than bypassing them.

Issue creation locks the project's settings row while allocating its next
number, so concurrent requests cannot create duplicate keys. The command
services also reject reporters, assignees, parents, statuses, and transition
targets that cross the project or workspace boundary.

```bash
source .venv/bin/activate
python backend/manage.py migrate
python backend/manage.py test apps.accounts apps.workspaces apps.projects apps.issues -v 2
```

## Step 5: REST API

All REST endpoints require an authenticated Django session and scope reads by
workspace or project membership before serializing data. Writes delegate to the
domain services, so HTTP requests cannot bypass the transaction and tenant
checks implemented in earlier steps.

| Endpoint | Operations |
| --- | --- |
| `/api/v1/workspaces/` | List accessible workspaces; create a workspace |
| `/api/v1/workspaces/{workspace_id}/teams/` | List teams; admins create teams |
| `/api/v1/workspaces/{workspace_id}/projects/` | List visible projects; admins create projects |
| `/api/v1/projects/{project_id}/issues/` | Paginated issue list; create issue |
| `/api/v1/issues/{issue_id}/transition/` | Move through a configured workflow transition |

Issue listing supports `?page=2`, `?page_size=50` (maximum 100), and an
optional `?status={status_uuid}` filter. Confirm the API foundation with:

```bash
python backend/manage.py check
python backend/manage.py test apps.accounts apps.workspaces apps.projects apps.issues -v 1
```

## Step 8: real-time project boards

An authenticated browser session can connect to:

```text
ws://localhost:8000/ws/projects/{project_uuid}/board/
```

The consumer validates project visibility before accepting the connection and
returns close code `4403` for unauthorized users. It is server-driven: issue
creation, transitions, comments, and attachments emit compact events only
after the database transaction commits. Clients should refetch the changed
issue when they receive an event; this keeps WebSocket payloads small and
prevents stale-board writes.

Docker Compose sets `USE_REDIS_CHANNEL_LAYER=true`, using Redis to share groups
across Daphne/Gunicorn processes. Local development safely defaults to an
in-memory channel layer when Redis is not running.

```bash
docker compose up --build
python backend/manage.py test apps.issues.test_realtime -v 2
```

## Step 9: custom fields and issue search

Projects can define text, dropdown, date, user-picker, and multi-select custom
fields. Values are stored once per issue/field pair and are rejected unless the
field belongs to that issue's project and matches the configured type.

| Endpoint | Purpose |
| --- | --- |
| `GET/POST /api/v1/projects/{id}/custom-fields/` | List fields or configure a field |
| `GET/POST /api/v1/projects/{id}/filters/` | List accessible saved filters or save one |
| `GET /api/v1/projects/{id}/issues/` | Filter with query parameters or `jql` |

Supported query parameters include `status`, `priority`, `issue_type`,
`assignee`, `reporter`, `label`, and free-text `q`. JQL-lite is intentionally
bounded, for example: `priority = high AND type = bug`. This avoids exposing
raw ORM/database query syntax to API clients.

## Step 7: collaboration and audit trail

Issues now support Markdown comments, email-style mentions such as
`@person@example.com`, per-user notifications, append-only activity entries,
and guarded uploads. A mention is resolved only when that email belongs to a
membership in the issue's workspace; the author is never self-notified.

| Endpoint | Purpose |
| --- | --- |
| `GET/POST /api/v1/issues/{id}/comments/` | Read or add a Markdown comment |
| `GET/POST /api/v1/issues/{id}/attachments/` | Read metadata or upload an attachment |
| `GET /api/v1/issues/{id}/activity/` | Read the audit trail |
| `GET /api/v1/notifications/` | Read the current user's inbox |
| `POST /api/v1/notifications/{id}/read/` | Mark one notification read |

Uploads have a 10 MB default limit and use a strict extension/MIME allow-list.
They are stored with a `pending` scan state and are deliberately not served by
a public media URL. A later background scanning step will mark files clean and
introduce an authorized download endpoint.

```bash
python backend/manage.py migrate
python backend/manage.py test apps.accounts apps.workspaces apps.projects apps.issues -v 1
```

## Step 6: authentication

Session-based browser authentication and bearer-token authentication are both
available. Passwords are validated against Django's built-in validators and
stored with Django's configured password hasher (Argon2 is installed for
production use). Password reset requests always return `202`, whether or not
the email exists, to prevent account enumeration.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/auth/register/` | Create an account and begin a browser session |
| `POST /api/v1/auth/login/` | Begin a browser session |
| `POST /api/v1/auth/logout/` | End the current browser session |
| `GET /api/v1/auth/me/` | Return the current user |
| `POST /api/v1/auth/password-reset/` | Request a one-time reset email |
| `POST /api/v1/auth/password-reset/confirm/` | Confirm UID/token and set a password |
| `POST /api/v1/auth/token/` | Obtain access and refresh JWTs |
| `POST /api/v1/auth/token/refresh/` | Rotate a refresh JWT into a new pair |
| `POST /api/v1/auth/token/revoke/` | Revoke a refresh JWT |

Access tokens expire after 15 minutes. Refresh-token IDs are persisted and a
token is revoked during rotation, logout/revocation, or password reset; a
stolen refresh token therefore cannot be replayed after use. Set a separate
`JWT_SIGNING_KEY` in production.

```bash
python backend/manage.py migrate
python backend/manage.py test apps.accounts apps.workspaces apps.projects apps.issues -v 1
```
