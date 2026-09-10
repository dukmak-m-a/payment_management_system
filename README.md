# NGO Compliance Tracking App

A Flask and Supabase application for tracking projects, payments, invoices,
receipts, and the compliance documents needed to close donor-funded work.

The compliance report is designed to fail safe: a document is never shown as
complete merely because a stored status became stale. Human-controlled slots
are stored as requirements; invoice and receipt slots are computed live from
the underlying records.

## Stack

- Python / Flask backend
- Supabase PostgreSQL database
- Vanilla JavaScript and CSS frontend
- Flask session authentication

## Local setup

Create and activate a virtual environment, then install the minimal runtime
dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root. Do not put spaces around `=` and do
not commit this file:

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-server-only-supabase-key
FLASK_SECRET_KEY=generate-a-long-random-secret
```

Generate the Flask secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Run the app locally:

```bash
python app.py
```

Open <http://127.0.0.1:5000>. The development server is loopback-only; do not
expose Flask's debug server to a network.

## Database setup

The reference schema, including `Accounts`, is in [agent.md](agent.md). Run
the SQL in this order from the Supabase SQL editor:

1. Create the base tables described in `agent.md`.
2. Run [sql/phase4_requirements.sql](sql/phase4_requirements.sql) to create
   requirements tables and compliance views.
3. Run [sql/phase5_integrity_hardening.sql](sql/phase5_integrity_hardening.sql).
   It performs fail-closed preflight checks before adding integrity constraints;
   resolve any reported legacy data before rerunning it.

Create the first user manually in `Accounts`. Use `python generate_hash.py` to
produce a password hash, then store that hash—not the plain password—in the
database.

## Compliance model

The report contains two kinds of slots:

- Human-edited requirements: `Missing`, `Unnecessary`, `Requested`, or
  `Collected`.
- Computed document status: invoices use amount coverage against non-returned
  payments; receipts use the status of the payment's one receipt row.

`Closed` is calculated on every report read. It becomes `Yes` only when every
required slot is `Collected` or `Unnecessary`.

The detailed schema, API surface, and known implementation constraints live in
[agent.md](agent.md). Design reasoning and domain decisions live in
[project-context.md](project-context.md).

## Security notes

- Keep the Supabase server key in `.env` only; never expose it to browser code.
- Rotate a key immediately if it may have been copied, logged, or shared.
- Before deployment, use HTTPS, a production WSGI server, a secure session
  cookie, rate limiting, and Supabase RLS. See `agent.md` for the checklist.
