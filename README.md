# Quantum Drug Discovery

A precision-oncology console: doctors upload a patient dataset, the backend runs
a Qiskit quantum feature analysis alongside a scikit-learn drug-response model,
and per patient can pull a live, evidence-ranked list of real drugs targeting
their recorded gene mutation for their cancer type.

- **Backend**: Flask, SQLAlchemy + Alembic, JWT auth, Qiskit, scikit-learn
- **Frontend**: React 19 + Vite, React Router, a glassmorphic/neumorphic UI

---

## Genomic drug recommendations (`/api/recommend`)

Given a gene symbol and cancer type, `backend/genomics.py` queries the
[Open Targets Platform](https://platform.opentargets.org/) GraphQL API live —
nothing here is a static or fabricated dataset. It resolves the gene to a
target ID, pulls every drug in clinical development or approved against that
target, filters to the ones with documented evidence in the given cancer
type, and ranks them by clinical stage (approved > phase 3 > ... ). Results
are cached per gene in the `genomics_cache` table for 24h so repeat lookups
are instant and don't hammer the public API.

**This intentionally does not fabricate a result when there isn't one.**
Tumor-suppressor genes like BRCA1/BRCA2 correctly come back with zero direct
matches — they aren't drug targets themselves, the real clinical intervention
(PARP inhibitors) works through a different target via synthetic lethality.
The UI explains this rather than hiding it or inventing a fake match. If you
want to extend this to also surface indirect/synthetic-lethality relationships,
that needs a second, separate evidence source — it's not something the
direct target→drug lookup can honestly produce.

---

## For a team: use Docker

If more than one person is running this, **use the Docker path below, not the
manual one.** Docker pins the exact OS, Python, and Node versions inside the
images, so everyone gets byte-for-byte the same environment regardless of
what's installed on their laptop. The manual path is fine for solo quick
edits, but "works on my machine" bugs almost always come from Python/Node
version drift between contributors — Docker removes that variable entirely.

## Quick start (Docker)

This is the fastest path to a fully working stack (Postgres + backend + frontend).

```bash
cp .env.example .env
# then edit .env and set SECRET_KEY (see the comment in the file for how to generate one)
docker compose up --build
```

Open **http://localhost:8080**. Sign in with the seeded demo account:
`doctor@gmail.com` / `password123`.

The frontend container serves the built React app via nginx and proxies `/api/*`
to the backend container, so there's no CORS configuration to worry about in
this setup. The backend container runs `flask db upgrade` automatically on
startup before serving traffic.

To stop: `docker compose down`. To wipe the database too: `docker compose down -v`.

---

## Local development (without Docker)

Use the same versions as CI/Docker so behavior matches across every
contributor's machine: **Python 3.12** (pinned in `backend/.python-version`)
and **Node 22** (pinned in `frontend-app/.nvmrc` / `package.json engines` —
`npm install` will refuse to run on the wrong Node version). If you use
`pyenv`/`nvm`, running `pyenv install` / `nvm use` in each folder picks up
the pinned version automatically.

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate   |   macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # edit SECRET_KEY at minimum
flask db upgrade       # creates backend/users.db and applies migrations
python app.py          # http://127.0.0.1:5000, debug reloader on if FLASK_DEBUG=true
```

### Frontend

```bash
cd frontend-app
npm install
cp .env.example .env   # VITE_API_URL should point at the backend above
npm run dev             # http://localhost:5173
```

### Running the test suites

```bash
# backend
cd backend && pytest -v

# frontend
cd frontend-app && npm run test
```

Both suites run in CI on every push/PR — see `.github/workflows/ci.yml`.

---

## Database migrations

Schema changes go through Alembic via Flask-Migrate:

```bash
cd backend
flask db migrate -m "describe the change"   # generates a migration file
flask db upgrade                             # applies it
```

Commit the generated file under `backend/migrations/versions/`. In production,
run `flask db upgrade` as part of your deploy step before the new app version
starts serving traffic (the Docker image's entrypoint does this automatically).

---

## Environment variables

### Backend (`backend/.env`, see `backend/.env.example`)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | JWT signing key | none — must be set |
| `DATABASE_URL` | SQLAlchemy connection string | SQLite at `backend/users.db` |
| `FRONTEND_ORIGIN` | Allowed CORS origin | `http://localhost:5173` |
| `FLASK_DEBUG` | Enables the Werkzeug debugger/reloader | `false` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Outbound email for password resets | unset — reset emails are logged to stdout instead of sent |

### Frontend (`frontend-app/.env`, see `frontend-app/.env.example`)

| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_URL` | Backend base URL, baked in at build time | `http://127.0.0.1:5000/api` |

### Docker Compose (repo-root `.env`, see `.env.example`)

Covers `SECRET_KEY`, Postgres credentials, `FRONTEND_ORIGIN`/`FRONTEND_PORT`, and
the same SMTP variables.

---

## Deploying somewhere real

The Docker images are host-agnostic — push them to any container registry and
run them on Render, Railway, Fly.io, ECS, a VM, etc. Three things to set up
wherever you land:

1. **A real Postgres instance.** Point `DATABASE_URL` at it and run
   `flask db upgrade` once before the first deploy.
2. **Persistent volumes are not required for app data** — uploaded patient
   files are deleted immediately after each analysis request completes (see
   "Data handling" below). You only need a volume for Postgres itself.
3. **`SECRET_KEY`** as a real secret in your host's secret manager, not
   committed anywhere.

The backend serves via `waitress` (cross-platform, no `debug=True` Werkzeug
server in the request path). Flask-Limiter's rate limiter currently uses
in-memory storage, which is fine for a single backend instance; if you scale
to multiple backend replicas, point it at Redis instead (`storage_uri` in
`extensions.py`) so rate limits are shared across instances.

---

## Data handling

Patient data (uploaded CSVs, quantum scores, predictions) is **not persisted**
on the server. Files are processed in-memory/on-disk for the duration of a
single `/api/upload` request and deleted immediately afterward, whether the
request succeeds or fails. The only thing that outlives a request is an audit
log entry (`audit_logs` table) recording *that* an upload happened — who, when,
how many rows — never the patient data itself.

This app has **not** been reviewed for HIPAA/GDPR compliance and doesn't
implement per-user data isolation, encryption at rest, or a signed data
processing agreement. It's suitable for demos and internal tooling with
synthetic/de-identified data. Don't point it at real patient records without
a proper compliance review first — that's a legal/organizational undertaking,
not something a codebase can certify on its own.

---

## Project layout

```
backend/
  app.py               Flask app factory, error handlers, logging
  auth.py               /api/auth/* — register, login, me, password reset
  routes.py              /api/upload, /api/health
  models.py               SQLAlchemy models (User, AuditLog)
  extensions.py             db / migrate / limiter instances
  preprocessing.py           cleans + encodes uploaded CSVs
  quantum/quantum_model.py     Qiskit feature-encoding circuit
  predict.py                    scikit-learn drug-response prediction
  migrations/                     Alembic migration history
  tests/                            pytest suite

frontend-app/
  src/pages/            Login, Register, ForgotPassword, ResetPassword, Dashboard, NotFound
  src/context/           AuthContext (JWT session), ToastContext (notifications)
  src/components/         Navbar, Dropzone, Pagination, ProtectedRoute, ErrorBoundary
  src/styles/theme.css      glass + neumorphic design system
```
