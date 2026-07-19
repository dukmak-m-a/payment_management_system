# NGO Compliance Tracking App — Project Context

**Purpose of this document:** Portable context for continuing this build in Claude
Code / new chat. It captures decisions actually made, the reasoning behind them, and
what is still open. It is not a finished spec — treat unresolved items as blockers
to work through before building on top of them, not assumptions to build around.

---

## 1. Business Context

- Client domain: Türkiye-based NGO / donor-funded program compliance tracking.
- Compliance specialist manually tracks 15–25 payments/month, each requiring
  15–20 supporting documents (invoices, receipts, translations, bank documents,
  photos, decision documents), to be collected within **90 days of payment date**
  per Turkish regulatory requirement.
- Currently multiple employees are needed to keep this on track in larger orgs —
  the core pain is coordination and visibility, not just data entry.
- This is portfolio/case-study project #1 for a freelance automation business
  targeting the NGO/M&E compliance niche (see career context in Section 7).

## 2. System Evolution (know which one you're building)

1. **Legacy (still live):** Google Sheet (one row per payment, 12 document-type
   columns each Missing/Requested/Collected, plus a rollup "Done" column) +
   n8n workflow (schedule trigger → filter Missing → Summarize x2 → JS Code node
   → Gmail **draft**, not auto-send).
2. **In development (the actual target now):** A relational app (tables below)
   replacing both the spreadsheet and the ad hoc Drive folder system. Local v1
   is usable. n8n will be re-pointed from Sheets to this app's database.

**Decision: build forward on the app, not the spreadsheet.** The spreadsheet
workflow stays running as-is until the app replaces it; don't invest further
design effort in the Sheets version.

## 3. Core Architectural Decisions (the "why")

These principles should govern every design choice below, including ones not
yet made:

- **Risk asymmetry is the north star.** A false "Missing" is self-correcting —
  it triggers human review, and the specialist replies "already sent." A false
  "Collected/Done" is dangerous — it silently hides a real compliance gap that
  nobody ever checks again. Every automated status-write must be biased toward
  under-claiming completion, never over-claiming it.
- **Two-key identity model.**
  - **Company/Supplier code** → keys the contact-person lookup (one contact
    person per supplier; multiple emails supported, sent to all).
  - **Project code = Decision Number** → keys which document/row a given
    payment or upload belongs to. One supplier can have multiple projects
    (multiple decision numbers) over time.
  - Drive folder structure: `projects/[project_code]/` — the
    folder connect to the project row in the database, the database provides company code for contact lookup, full
    project code for row-matching. This avoids fragile filename parsing.
- **Staging over confirmation-bot.** Unverified/ambiguous documents get a
  `to_verify` status (not Missing, not Received) and are held in a separate
  `verifying` Drive folder, distinct from project folders, until a human
  confirms. After verification: either marked Received, or discarded as wrong
  with no row ever edited. No Telegram/WhatsApp bot needed for v1 — the
  staging area *is* the confirmation mechanism.
- **Codes are auto-populated at creation time, not re-entered per document.**
  When a Project or Payment is created, Project/Payment codes cascade
  automatically into the Invoices/Receipts rows created alongside them. The
  specialist only fills in *missing document details* on an existing row, not
  free-text identifiers — this removes most of the mis-keying risk, except at
  the initial Project/Payment creation dropdown (see Open Issues).
- **Formalizing an existing checkpoint, not inventing one.** The legacy
  workflow already used Gmail *drafts* (human sends manually), i.e. an
  informal human-in-the-loop already exists. The new system should preserve or
  upgrade that checkpoint, not remove it in the name of "automation."

## 4. Current Schema (as of this session, with fixes applied)

Six tables: **Suppliers, Donors, Decisions, Projects, Payments, Invoices,
Receipts.** (Requirements table not yet built — see Section 5.)

Key fields per table (not exhaustive — see actual `tableConfigs` in the app
code for full field lists):

- **Suppliers**: `CompanyName`, `Country`, `ContactPerson` (external — who you
  request documents *from*). (`TaxId` dropped 2026-07-19.)
- **Donors**: `DonorCode`, `DonorName`, `Country`, `ContactPerson`.
- **Decisions**: `DecisionNumber`, `DecisionDate`, `Description`, `Attendants`.
- **Projects**: `ProjectCode`, `Subject`, `SupplierId`, `Budget`, `Currency`,
  `StartDate`, `EndDate`, `Status` (Active/Completed/On-Hold/Cancelled),
  `DriveFolderLink`.
- **Payments**: `PaymentCode`, `SupplierId`, `ProjectId`, `DonorId`,
  `DecisionId`, `Destination` (Domestic/International), `Bank`, `Amount`,
  `Currency`, `Status` (Sent/Declared/Closed/Returned/Return-Closed),
  `PaymentDate`, `DeclarationDate`, `ClosingDate` — **fix applied: these last
  two are now included in `columns`, previously only in `formFields`.**
  (`Payments.ReceiptCode` was dropped 2026-07-19 — removed from the DB and from
  `update_payment()`.)
  `DaysToClose` is **computed at read time, not stored**:
  ```python
  if payment.get("ClosingDate"):
      payment["DaysToClose"] = None
  elif payment.get("PaymentDate"):
      payment_date = datetime.strptime(payment["PaymentDate"], "%Y-%m-%d").date()
      payment["DaysToClose"] = 90 - (today - payment_date).days
  else:
      payment["DaysToClose"] = None
  ```
- **Invoices**: `InvoiceCode`, `No`, `SupplierId`, `DonorId`, `ProjectCode`,
  `Date`, `Amount`, `Currency`, `Status`, `Notes`.
- **Receipts**: `ReceiptCode`, `No`, `ProjectCode`, `PaymentCode`,
  `PaymentDate`, `ReceiptDate`, `Amount`, `Currency`, `Status`,
  `RequiresTranslation`, `AssignedTo`, `Notes`. The `Date`-vs-`ReceiptDate`
  naming mismatch was fixed earlier. **Domain rule (Abdullah, 2026-07-19): a
  receipt's `Amount`/`Currency` can legitimately differ from its payment's
  (bank cut / commission), so any payment→receipt sync must NEVER overwrite
  receipt money fields — the gap between `Receipt.Amount` and the joined
  `PaymentAmount` is itself a compliance signal.** (Feeds the Phase-4 cascade.)
- **Status (unified)** on Invoices and Receipts — **APPLIED IN CODE 2026-07-19**
  (was only *decided* until then — the running frontend still carried staff-name
  statuses + the `Fatura`/`Makbuz` fields through 2026-07-18, a third confirmed
  doc-drift instance). Previously two overlapping fields (`Status` with staff
  names baked in, e.g. "Requested Ahmet"; and a separate `Fatura`/`Makbuz` field
  with near-duplicate stages). Now one `Status` enum:
  `Missing → Requested → Received → Translated → Sent → Done`, staff names
  removed. Two new fields added alongside on both tables: `RequiresTranslation`
  (boolean, default `true`) and `AssignedTo` (text) — the latter closes Open
  Issue #1. `Fatura`/`Makbuz` columns dropped from the DB.

## 5. Open Issues (unresolved — do not build past these silently)

1. **Internal assignee gap — RESOLVED 2026-07-19.** Merging Status removed the
   "Requested Ahmet" / "Requested Heba" distinction (which internal staff member
   currently owns a document for translation/signing — not `Supplier.ContactPerson`,
   who is external). Resolved by adding an `AssignedTo` text field to
   Invoices/Receipts: single current holder, no history (overwrite loses the
   prior name — accepted tradeoff).
2. **Requirements table does not exist yet.** No schema, no cascade/trigger
   logic. This is the next concrete build task. Cascade behavior agreed in
   principle: an Invoice/Receipt Status change updates the linked Requirements
   row/column for that document type — but the actual implementation
   (DB trigger? application logic on write? scheduled reconciliation?) is
   undecided.
2b. **`to_verify` status integration**: confirmed conceptually (Section 3) but
   not yet reflected in the not-yet-built Requirements table's status enum.
3. **Status pipeline isn't strictly linear across document types** — e.g. not
   every document type requires a `Translated` step (Bank Receipt didn't in
   the legacy sheet; Invoice and Company Receipt did). The cascade logic needs
   to handle "skip this stage for this document type," not assume every row
   passes through all six Status values.
4. **Mis-selection risk at Project/Payment creation.** Auto-populating codes
   downstream removes most mis-keying risk, but the initial dropdown selection
   of Supplier/Project when creating a Payment is still manual and unvalidated.
   Flagged as a v2 concern, not a blocker for v1.
5. **Schema audit — field-level pass done 2026-07-19.** The other four tables
   (Suppliers, Donors, Decisions, Projects) were run through the three-way,
   both-directions audit (columns ↔ formFields ↔ backend dict) and all four
   **PASS** — no field mismatch remains. Suppliers was additionally verified
   end-to-end via a live create after the `TaxId` drop; a belt-and-suspenders
   end-to-end test row for Donors/Decisions/Projects is still worth doing but
   nothing is known broken.
6. **n8n ↔ database integration not yet built.** Plan (agreed, not
   implemented): n8n stops reading Google Sheets on a schedule and instead
   pulls from the app's database; Drive folder creation switches from
   whatever triggers it today to a webhook fired when a new Project is
   created in the app.

## 6. Working Style — how to continue this

Abdullah is building this as a real skill, not outsourcing the thinking. The
mentorship pattern that's worked so far: guiding questions before solutions,
failure-mode analysis ("what goes wrong if this is wrong") to drive
architecture decisions, and code/schema review focused on reliability and
edge cases, not just "does it run." When continuing in Claude Code, prefer
surfacing tradeoffs and asking which failure mode is acceptable over silently
picking one and generating code — especially for anything that writes to the
Requirements table or triggers a status cascade, given the risk-asymmetry
principle in Section 3.

## 7. Career Context (brief)

This project is Month 1's flagship portfolio piece in a freelance automation
career plan targeting NGO/M&E/compliance clients (secondary niche: general
business ops automation). Client-facing artifacts (case study writeups,
the six-part problem/process/automation/data-model/human-in-the-loop/
out-of-scope spec) are a separate deliverable from this technical context doc
— useful to produce once the Requirements table and cascade logic are real,
not before.
