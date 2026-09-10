# API and Backend Contract

## API style

Serve templates and JSON from one Flask app. The browser uses same-origin requests. Every `/api/*` route returns JSON; unauthenticated API requests return `401` JSON, while pages redirect to `/login`.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/` | Render application shell. |
| GET/POST | `/login` | Render or process login form. |
| POST | `/logout` | Clear session and redirect to login. |
| GET | `/api/suppliers`, `/api/donors`, `/api/decisions` | List lookup data. |
| GET | `/api/projects` | List projects with supplier display name. |
| GET | `/api/payments` | List payments with joined names and calculated `DaysToClose`. |
| GET | `/api/invoices` | List invoices with joined supplier/donor names. |
| GET | `/api/receipts` | List receipts with a display-only payment code field. |
| POST | `/api/{entity}` | Create one supported entity. |
| PUT | `/api/{entity}/{id}` | Partial update: omit field to preserve it; send `null` to clear optional field. |
| DELETE | `/api/{entity}/{id}` | Delete supported entity; report FK conflict readably. |
| GET | `/api/compliance_report` | Read the wide SQL view, newest transfers first. |
| PUT | `/api/requirements` | Upsert one human requirement slot. |

Supported CRUD entities: `suppliers`, `donors`, `decisions`, `projects`, `payments`, `invoices`, `receipts`.

## Input policy

- Define explicit field allowlists per entity. Never pass arbitrary JSON to Supabase.
- For updates, construct a patch from fields actually present in JSON; do not use `data.get()` for every field because omitted values would overwrite existing values with null.
- Validate required fields, enum values, currency, and finite non-negative amounts before writing.
- Convert `RequiresTranslation` from form strings. Blank/missing must become `true`, never null/false.
- Return `{ "success": true, "id": ... }` on create and `{ "success": true }` on updates/deletes. Return `{ "success": false, "error": "safe message" }` on client errors.

## Required GET transformations

- Projects: join `Suppliers(CompanyName)` and flatten `SupplierName` for the table.
- Payments: join supplier/project/donor/decision display fields. Calculate `DaysToClose = 90 - (today - PaymentDate).days`; return null when `ClosingDate` is present or payment date is absent.
- Receipts: keep raw numeric `PaymentCode` for the edit control, and add a second `paymentCodeDisplay` from the joined payment. Never overwrite the raw FK with text.

## Requirement update payload

```json
{
  "scope": "payment",
  "doc_type": "Dekont",
  "status": "Collected",
  "owner_id": 42
}
```

Allow only payment docs (`Dekont`, `TransferOrder`, `OdemeEmri`) on `PaymentRequirements` and project docs (`Contract`, `Karar`, `TeslimBelgesi`, `AlindiBelgesi`, `Fotograflar`) on `ProjectRequirements`. Reject any attempt to write Invoice, Receipt, Fatura, or Makbuz slots.

## Authentication contract

- Keep public endpoints allowlisted by Flask endpoint name: only `login` and `static`.
- All other routes require a session user ID. This default-deny structure is safer than remembering decorators on every new route.
- Look up `Accounts` by username. Check a dummy password hash for unknown users to reduce username timing leaks. Use one generic error for bad username/password/disabled account.
- Call `session.clear()` before setting user fields after successful login, set an 8-hour permanent session, and clear it on logout.
- Throttle repeated login failures (current local target: five attempts in fifteen minutes per username). Replace with durable per-IP and per-username rate limiting before production.

## Error and transaction notes

During local development, keep exceptions visible in server logs. Before deployment, log server-side and return generic client messages so SQL structure and credentials are never exposed. Creation side effects should ultimately be atomic; until they are, test and document how to repair a partial project/payment creation.
