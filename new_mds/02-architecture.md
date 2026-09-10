# Architecture and Project Layout

## Chosen architecture

```text
Browser (one-page vanilla JS UI)
        │ same-origin JSON / form requests
        ▼
Flask application
  ├─ session authentication
  ├─ validation and business rules
  ├─ HTML templates and static assets
  └─ Supabase Python client, scoped to one request
        │
        ▼
Supabase PostgreSQL
  ├─ base tables and foreign keys
  ├─ constraints/triggers
  └─ live compliance views
```

This is intentionally a simple monolith. It lets you learn HTTP, validation, SQL, sessions, and DOM work without a frontend framework or a second deployment.

## Suggested project tree

```text
ngo-compliance-tracker/
├── app.py
├── requirements.txt
├── .env                 # never commit
├── .env.example
├── generate_hash.py
├── sql/
│   ├── 001_base_schema.sql
│   ├── 002_requirements_and_views.sql
│   └── 003_integrity_hardening.sql
├── templates/
│   ├── index.html
│   └── login.html
├── static/
│   ├── app.js
│   └── style.css
└── tests/               # add as you learn testing
```

## Responsibilities

| Layer | Owns | Must not own |
|---|---|---|
| PostgreSQL | relationships, unique constraints, invariant enforcement, computed report | browser presentation |
| Flask | auth, JSON parsing, allowlists, validation, safe errors | duplicated compliance formulas |
| JavaScript | table rendering, modal forms, lookup selection, local UI preferences | secrets or completion decisions |
| CSS/HTML | accessibility and visual feedback | business rules |

## Local configuration

Use a `.env` file with only server-side values:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=YOUR_SERVER_SIDE_KEY
FLASK_SECRET_KEY=long-random-value
```

Generate the session secret with `python -c "import secrets; print(secrets.token_hex(32))"`. Do not expose any Supabase privileged key in browser JavaScript.

## Dependency baseline

```text
Flask
python-dotenv
supabase
Werkzeug
```

## Request-scoped Supabase client

Create the Supabase client inside Flask's request context (store it on `flask.g`), not once globally. A shared synchronous client can share connection/session state across concurrent web requests and cause intermittent failures. Expose a helper or `LocalProxy` so routes still read naturally.

## Development order

Use database → backend → frontend for every feature. A UI field with no API support silently loses data; an API field with no DB support fails at runtime. The roadmap makes this sequence explicit.
