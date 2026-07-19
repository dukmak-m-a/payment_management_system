# agent.md — Payment / Compliance Document Tracking Engine — Technical Reference

## Role of this file

This is the **what**: exact DB schema, API endpoints, and known
implementation gotchas for the current codebase. It's written to be generic
and reusable across deployments — the only client-specific values live in
"Branding & Design" below, clearly marked as placeholders.

- For the business narrative and architectural decisions behind the current
  deployment (NGO/donor compliance tracking), see `project-context.md`.
- For how Claude Code should behave while working in this repo, see
  `CLAUDE.md`.

Don't duplicate content across these three files — if something changes,
update it in the one file whose job it is, not all three.

---

## Project Overview

A full-stack web application for managing payments, projects, suppliers,
donors, decisions, invoices, and receipts. Built with Flask (Python) backend
and vanilla JS frontend, using Supabase (PostgreSQL) as the database.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask, flask-cors |
| Database | Supabase (PostgreSQL) via `supabase-py` |
| Frontend | Vanilla JS, HTML5, CSS3 (no framework) |
| Fonts | Configurable — see Branding & Design |

### Install dependencies
```bash
pip install Flask flask-cors supabase
```

### Run the app
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-or-service-role-key"
python app.py
# Access at http://localhost:5000
```

---

## File Structure

```
project/
├── app.py                  # Flask backend — all API routes
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Single page app shell + navigation
└── static/
    ├── app.js              # All frontend logic, table configs, CRUD
    └── style.css           # Styling, theme (see Branding & Design)
```

---

## Database Schema (Supabase / PostgreSQL)

> Verified directly against a live Supabase schema export (not reconstructed
> from application code). **Updated 2026-07-19 after the Status-merge migration
> landed:** `Fatura` (Invoices), `Makbuz` (Receipts), `Payments.ReceiptCode`,
> and `Suppliers.TaxId` have all been **dropped**; `RequiresTranslation`
> (boolean, default `true`) and `AssignedTo` (text) were **added** to Invoices
> and Receipts. The DDL below reflects the post-migration schema. (Gotchas #7
> and #8 are now resolved — kept below for history.)

```sql
-- WARNING: schema is for reference only, not meant to be run as-is.
CREATE TABLE public.Suppliers (
  id bigint NOT NULL DEFAULT nextval('"Suppliers_id_seq"'::regclass),
  CompanyName text NOT NULL,
  Country text,
  ContactPerson text,
  CONSTRAINT Suppliers_pkey PRIMARY KEY (id)
);

CREATE TABLE public.Donors (
  id bigint NOT NULL DEFAULT nextval('"Donors_id_seq"'::regclass),
  DonorCode text NOT NULL UNIQUE,
  DonorName text NOT NULL,
  Country text,
  ContactPerson text,
  CONSTRAINT Donors_pkey PRIMARY KEY (id)
);

CREATE TABLE public.Decisions (
  id bigint NOT NULL DEFAULT nextval('"Decisions_id_seq"'::regclass),
  DecisionNumber text NOT NULL UNIQUE,
  DecisionDate date,
  Description text,
  Attendants text,
  Notes text,
  CONSTRAINT Decisions_pkey PRIMARY KEY (id)
);

CREATE TABLE public.Projects (
  id bigint NOT NULL DEFAULT nextval('"Projects_id_seq"'::regclass),
  ProjectCode text NOT NULL UNIQUE,
  Subject text NOT NULL,
  Description text,
  SupplierId bigint NOT NULL,
  Budget numeric,
  Currency text,
  StartDate date,
  EndDate date,
  DriveFolderLink text,
  Status text DEFAULT 'Active'::text,
  CONSTRAINT Projects_pkey PRIMARY KEY (id),
  CONSTRAINT Projects_SupplierId_fkey FOREIGN KEY (SupplierId) REFERENCES public.Suppliers(id)
);

CREATE TABLE public.Payments (
  id bigint NOT NULL DEFAULT nextval('"Payments_id_seq"'::regclass),
  PaymentDate date,
  PaymentCode text,
  Amount numeric,
  Currency text,
  ProjectId bigint NOT NULL,
  SupplierId bigint NOT NULL,
  Destination text,
  DonorId bigint,
  DecisionId bigint,
  Bank text,
  Status text,
  DeclarationDate date,
  ClosingDate date,
  CONSTRAINT Payments_pkey PRIMARY KEY (id),
  CONSTRAINT Payments_ProjectId_fkey FOREIGN KEY (ProjectId) REFERENCES public.Projects(id),
  CONSTRAINT Payments_SupplierId_fkey FOREIGN KEY (SupplierId) REFERENCES public.Suppliers(id),
  CONSTRAINT Payments_DonorId_fkey FOREIGN KEY (DonorId) REFERENCES public.Donors(id),
  CONSTRAINT Payments_DecisionId_fkey FOREIGN KEY (DecisionId) REFERENCES public.Decisions(id)
);

CREATE TABLE public.Receipts (
  id bigint NOT NULL DEFAULT nextval('"Receipts_id_seq"'::regclass),
  ProjectCode text,
  PaymentCode bigint,        -- FK is numeric Payments.id, not the text PaymentCode
  PaymentDate date,
  ReceiptCode text,          -- the receipt document's OWN code (not the payment code)
  No text,
  ReceiptDate date,
  Amount numeric,            -- the RECEIPT's amount; may differ from the payment (bank cut/commission)
  Currency text,
  Status text,               -- six-stage: Missing/Requested/Received/Translated/Sent/Done
  RequiresTranslation boolean DEFAULT true,
  AssignedTo text,
  Notes text,
  CONSTRAINT Receipts_pkey PRIMARY KEY (id),
  CONSTRAINT Receipts_ProjectCode_fkey FOREIGN KEY (ProjectCode) REFERENCES public.Projects(ProjectCode),
  CONSTRAINT Receipts_PaymentCode_fkey FOREIGN KEY (PaymentCode) REFERENCES public.Payments(id)
);

CREATE TABLE public.Invoices (
  id bigint NOT NULL DEFAULT nextval('"Invoices_id_seq"'::regclass),
  SupplierId bigint,
  DonorId bigint,
  ProjectCode text,
  InvoiceCode text,
  No text,
  Date date,
  Amount numeric,
  Currency text,
  Status text,                -- six-stage: Missing/Requested/Received/Translated/Sent/Done
  RequiresTranslation boolean DEFAULT true,
  AssignedTo text,
  Notes text,
  CONSTRAINT Invoices_pkey PRIMARY KEY (id),
  CONSTRAINT Invoices_SupplierId_fkey FOREIGN KEY (SupplierId) REFERENCES public.Suppliers(id),
  CONSTRAINT Invoices_DonorId_fkey FOREIGN KEY (DonorId) REFERENCES public.Donors(id),
  CONSTRAINT Invoices_ProjectCode_fkey FOREIGN KEY (ProjectCode) REFERENCES public.Projects(ProjectCode)
);
```

---

## Key Relationships & FK Notes

- `Projects.SupplierId` → `Suppliers.id` (required)
- `Projects` has **no** `DonorId` — do not add donor joins to Projects queries
- `Payments.ProjectId` → `Projects.id` (required, numeric id)
- `Payments.SupplierId` → `Suppliers.id` (required)
- `Receipts.PaymentCode` → `Payments.id` (**BIGINT**, not the text `PaymentCode`)
- `Receipts.ProjectCode` → `Projects.ProjectCode` (text, not id)
- `Invoices.ProjectCode` → `Projects.ProjectCode` (text, not id)

---

## API Endpoints

All endpoints return JSON. Base URL: `http://localhost:5000`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/suppliers` | List all suppliers |
| GET | `/api/donors` | List all donors |
| GET | `/api/decisions` | List all decisions |
| GET | `/api/projects` | List projects with SupplierName joined |
| GET | `/api/payments` | List payments with joined names + DaysToClose |
| GET | `/api/receipts` | List receipts with joined PaymentCode text |
| GET | `/api/invoices` | List invoices with joined names |
| POST | `/api/{table}` | Create record |
| PUT | `/api/{table}/{id}` | Update record |
| DELETE | `/api/{table}/{id}` | Delete record |

Allowed tables for DELETE: `Donors, Suppliers, Decisions, Projects, Payments, Receipts, Invoices`
The DELETE route applies `.capitalize()` to the table name from the URL.

---

## Business Logic

### DaysToClose (Payments)
Calculated in Python on every GET, not stored in DB:
```python
if ClosingDate is set:
    DaysToClose = None
else:
    DaysToClose = 90 - (today - PaymentDate).days
```
Color coding in frontend: green ≥ 30 days, yellow < 30, red < 10.

### Auto-create Receipt on Payment
When a new payment is POSTed, a receipt is automatically created, inheriting
Project / Payment / Date / Amount / Currency from the payment:
```python
# After inserting payment:
payment_id = payment["id"]           # numeric — used as Receipts.PaymentCode FK

supabase.table("Receipts").insert({
    "ProjectCode":         project_code,   # resolved from ProjectId
    "PaymentCode":         payment_id,     # BIGINT FK -> Payments.id
    "PaymentDate":         data.get("PaymentDate"),
    "Amount":              data.get("Amount"),
    "Currency":            data.get("Currency"),
    "Status":              "Missing",      # never auto-mark a receipt collected
    "RequiresTranslation": True,           # matches DB default (added 2026-07-19)
}).execute()
```
**Bug fixed 2026-07-19:** this insert previously wrote `payment_code` (the TEXT
`PaymentCode`) into the BIGINT FK column — it threw a type error the moment a
payment carried any non-numeric PaymentCode, leaving the payment saved but the
auto-receipt un-created. It now uses the numeric `payment_id`. The receipt does
NOT store the text code anywhere; `get_receipts` resolves it live via the FK join.

### DriveFolderLink (Projects)
Stored as plain text URL. Rendered as a clickable folder icon in the table.

---

## Frontend Architecture (app.js)

### Global State
```javascript
let currentTable = 'payments';  // active tab
let currentData = [];           // data currently displayed
let editingId = null;           // null = add mode, number = edit mode
let lookupData = { suppliers, donors, projects, decisions, payments };
let columnOrders = {};          // persisted in localStorage
```

### tableConfigs
Each table has:
- `columns`: ordered list of fields to show in the table
- `displayNames`: human-readable column headers
- `formFields`: field definitions for the add/edit modal

**Do not assume `columns`, `formFields`, and the backend's insert/update dict
agree with each other.** All three need independent verification — see
Known Gotchas #7 and #8 for two real cases where they didn't.

### Lookup types in formFields
- `lookup: 'suppliers'` → uses `item.id` as value, `item.CompanyName` as label
- `lookup: 'donors'` → uses `item.id` as value, `item.DonorName` as label
- `lookup: 'projects'` → uses `item.id` as value, `ProjectCode - Subject` as label
- `lookup: 'projectsByCode'` → uses `item.ProjectCode` as value (for Receipts/Invoices FK)
- `lookup: 'decisions'` → uses `item.id` as value, `item.DecisionNumber` as label
- `lookup: 'payments'` → uses `item.id` as value, `PaymentCode — Amount Currency` as label

### Column order
Stored per-table in `localStorage` under key `columnOrders`.
If a ghost column appears (e.g. from old data), clear localStorage to reset.

---

## Branding & Design (personalize per deployment)

This is the only section of this file that should differ between client
deployments. Replace the placeholders below when setting up for a specific
client, then this note can be deleted for that deployment's copy.

| Setting | Placeholder | Notes |
|---|---|---|
| Primary/accent color | `<ACCENT_COLOR>` | hex value matching client brand |
| Logo | `<LOGO_URL>` | hosted image URL or local asset path |
| Organization name | `<ORG_NAME>` | shown in header/title |
| Theme | dark background, accent highlights | swap to light theme if requested |
| Fonts | `<HEADER_FONT>` / `<BODY_FONT>` | defaults used so far: Syne / Space Mono |

---

## Known Gotchas

1. **Supabase sequence desync** — if you get `duplicate key violates unique constraint` on insert, run:
   ```sql
   SELECT setval(pg_get_serial_sequence('"TableName"', 'id'), (SELECT MAX(id) FROM "TableName"));
   ```
   Run for all tables after any manual data import.

2. **Case-sensitive table names** — always quote table names in SQL: `"Payments"` not `payments`.

3. **Projects has no DonorId** — do not attempt to join Donors from Projects queries.

4. **Receipts.PaymentCode is BIGINT** — always pass `Payments.id` (integer), never the text `PaymentCode`.

5. **DELETE route uses `.capitalize()`** — URL table names are auto-capitalized, so `/api/payments/1` maps to `"Payments"`.

6. **localStorage column orders** — if wrong columns appear in the UI, clear `columnOrders` from localStorage and hard refresh.

7. **RESOLVED 2026-07-19 — `Fatura` (Invoices) / `Makbuz` (Receipts) dropped.** These were real DB columns the backend never wrote (the frontend offered a dropdown, but the four Invoice/Receipt endpoints built an explicit field list that omitted them, silently discarding any value). Both columns are now dropped from the DB and both form fields removed from `tableConfigs`. Kept for history.

8. **RESOLVED 2026-07-19 — `Payments.ReceiptCode` dropped.** It used to silently null on every `update_payment()` save (the form had dropped the field, but the backend still wrote `data.get("ReceiptCode")` → `None`). The column is now dropped and the key removed from `update_payment()`. **`Receipts.ReceiptCode` is a different, unrelated column on another table and stays** — it holds the receipt document's own code (that column is NOT the payment's text code; the earlier "stores the text PaymentCode" description was wrong). Kept for history.

9. **PARTLY RESOLVED 2026-07-19 — badge classes added.** `style.css` now has classes for the six-stage enum (`Missing/Requested/Received/Translated/Sent/Done`) plus `On-Hold` (Projects) and `Return-Closed` (Payments). Remaining cleanup (harmless): dead classes with no matching value anywhere — `status-pending`, `status-approved`, `status-rejected`, `status-paid`, `status-verified`, `status-suspended` — still present, worth pruning in Phase 6.

10. **RESOLVED 2026-07-19 — auto-create receipt FK bug.** `create_payment()`'s auto-receipt wrote the TEXT `PaymentCode` into the BIGINT `Receipts.PaymentCode` FK (would error on any non-numeric PaymentCode, leaving the payment saved but no receipt). Now writes the numeric `payment_id`. See Business Logic → Auto-create Receipt on Payment.

11. **Shared Supabase client is not concurrency-safe (mitigated, not fixed).** The single global `supabase` client (`app.py`) is shared across Flask's dev-server threads; concurrent requests collide on its socket → `500 [Errno 11] Resource temporarily unavailable` (EAGAIN). Surfaced when the UI fired 5 lookup fetches via `Promise.all`. **Mitigated 2026-07-19** by loading those lookups sequentially in `loadLookupData` — but that only removes the UI's own burst. The real fix (per-request / thread-local client, or a serialized server) is a **Phase 5** task, when n8n hits the API concurrently with the UI.

---

## Planned / Potential Features

- Export to Excel / PDF
- Import CSV data
- Dashboard & analytics
- Advanced filtering by date range, status, supplier
- User authentication
- Backup / restore
