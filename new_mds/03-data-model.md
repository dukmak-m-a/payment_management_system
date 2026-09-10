# Data Model and Compliance Rules

## Entity map

```text
Suppliers 1 ── * Projects 1 ── * Payments 1 ── 0..1 Receipts
                         │             │
                         │             ├── 1 Donor (optional)
                         │             └── 1 Decision
                         ├── * Invoices
                         └── * ProjectRequirements

Payments ── * PaymentRequirements
```

## Base tables

| Table | Essential fields | Notes |
|---|---|---|
| `Suppliers` | `id`, `CompanyName`, `Country`, `ContactPerson` | A supplier can own many projects/payments. |
| `Donors` | `id`, `DonorCode` unique, `DonorName`, `Country`, `ContactPerson` | Optional on payment/invoice. |
| `Decisions` | `id`, `DecisionNumber` unique, `DecisionDate`, `Description`, `Attendants`, `Notes` | A payment references its approval decision. |
| `Projects` | `id`, `ProjectCode` unique, `Subject`, `Description`, `SupplierId`, `Budget`, `Currency`, dates, `Status`, `DriveFolderLink` | One project currency. |
| `Payments` | `id`, `PaymentCode`, supplier/project/donor/decision IDs, amount, currency, status, dates | `ProjectId`, `SupplierId`, and `DecisionId` are required. |
| `Invoices` | `id`, supplier/donor IDs, `ProjectCode`, code/no/date/amount/currency, document state, translation fields, notes | Project-level coverage documents. |
| `Receipts` | `id`, `ProjectCode`, numeric `PaymentCode`, document fields | `PaymentCode` refers to **`Payments.id`**, not the display code. |
| `Accounts` | `id`, `Username` unique, `PasswordHash`, `DisplayName`, `IsActive`, `CreatedAt` | Manual account provisioning only. |

Use quoted PascalCase names consistently if reproducing the current Supabase schema (for example, `public."Payments"`). PostgreSQL lowercases unquoted identifiers.

## Enum values

| Field | Allowed values |
|---|---|
| Project status | `Active`, `Completed`, `On-Hold`, `Cancelled` |
| Payment status | `Sent`, `Declared`, `Closed`, `Returned`, `Return-Closed` |
| Invoice/receipt document status | `Missing`, `Requested`, `Received`, `Translated`, `Sent`, `Done` |
| Requirement status | `Missing`, `Unnecessary`, `Requested`, `Collected` |
| Project/payment/invoice currency | `TRY`, `USD`, `EUR` |

## Invariants to enforce twice

Validate in Flask for a friendly response, then enforce in PostgreSQL so direct SQL, future n8n jobs, and races cannot break the rules.

- Amounts must be non-negative; payment amount/currency/status and project currency must be present.
- Each payment and invoice must use its project's currency.
- A receipt may have a different amount/currency from its payment because bank commission can be meaningful evidence.
- A payment has at most one receipt (`UNIQUE ("PaymentCode")`).
- `RequiresTranslation` is non-null and defaults to `true` (the conservative default).
- A deleted payment/project cascades only its requirement rows. Think carefully before enabling other cascades.

## Creation side effects

When creating a project:

1. Insert the project.
2. Insert one draft invoice: same project code/supplier/currency, `Status = Missing`, `RequiresTranslation = true`.
3. Insert five `ProjectRequirements`, all `Missing`: `Contract`, `Karar`, `TeslimBelgesi`, `AlindiBelgesi`, `Fotograflar`.

When creating a payment:

1. Validate its project currency then insert payment.
2. Look up `Projects.ProjectCode` using numeric `ProjectId`.
3. Insert one draft receipt, with `PaymentCode = newly created Payments.id` (not the text payment code), and `Status = Missing`.
4. Insert three `PaymentRequirements`, all `Missing`: `Dekont`, `TransferOrder`, `OdemeEmri`.

Do these in a database transaction/RPC in a production-quality next iteration. The current target implements them sequentially, so include a manual recovery checklist if a later insert fails.

## Compliance calculation

The report is one row per payment and contains twelve document slots. Eight are editable human requirements; four are computed from invoice/receipt data and must never be directly writable.

| Scope | Slots | Source |
|---|---|---|
| Payment, human | Dekont, TransferOrder, OdemeEmri | `PaymentRequirements` |
| Project, human | Contract, Karar, TeslimBelgesi, AlindiBelgesi, Fotograflar | `ProjectRequirements` |
| Payment, calculated | Receipt, Receipt Translation | receipt status + translation flag |
| Project, calculated | Invoice, Invoice Translation | invoice coverage/statuses |

### Receipt rules

- Receipt = `Collected` if status is `Received`, `Translated`, `Sent`, or `Done`; `Requested` if status is `Requested`; otherwise `Missing`.
- Receipt Translation = `Unnecessary` when `RequiresTranslation = false`; `Collected` only when receipt status is `Done`; `Requested` for `Translated`/`Sent`; otherwise `Missing`.

### Invoice rules

- Spending to document = sum of non-returned payment amounts for the project.
- In-hand invoices = sum of project invoice amounts with status `Received`, `Translated`, `Sent`, or `Done`.
- Invoice = `Collected` only when in-hand invoices cover all spending; it is `Requested` when some invoice activity exists but coverage is short; otherwise `Missing`.
- If a payment amount/status is unknown, invoice compliance is `Missing`.
- Invoice Translation = `Unnecessary` if no project invoice needs translation; `Collected` only when invoice coverage is collected and every translation-requiring invoice is `Done`; otherwise follow the conservative requested/missing logic.

### Closed rule

`Closed = Yes` only when **every** report slot is `Collected` or `Unnecessary`; otherwise `No`. Calculate it in the SQL view every time it is read.

## Known design decision to make before real data

Changing a `ProjectCode` after invoices/receipts reference it needs an explicit policy. Either make codes immutable after creation or alter both foreign keys to use `ON UPDATE CASCADE`. Do not leave the default behavior as an accidental user experience.
