<!-- Destination: repo root, replaces the current project-context.md -->

# NGO Compliance Tracking App — Project Context

**Purpose of this document:** Portable context for continuing this build in Claude Code / a new
chat. It captures decisions actually made, the reasoning behind them, what is still open, and
the history of what's changed. It is not a finished spec — treat unresolved items as blockers to
work through before building on top of them, not assumptions to build around. Read on demand
(before touching schema or status logic), not loaded automatically — see `CLAUDE.md` for what
*is* always loaded.

---

## 1. Business Context

- Client domain: Türkiye-based NGO / donor-funded program compliance tracking.
- Compliance specialist manually tracks 15–25 payments/month, each requiring 15–20 supporting
  documents (invoices, receipts, translations, bank documents, photos, decision documents), to
  be collected within **90 days of payment date** per Turkish regulatory requirement.
- Currently multiple employees are needed to keep this on track in larger orgs — the core pain
  is coordination and visibility, not just data entry.
- This is portfolio/case-study project #1 for a freelance automation business targeting the
  NGO/M&E compliance niche (see career context in §9).

## 2. System Evolution (know which one you're building)

1. **Legacy (still live):** Google Sheet (one row per payment, 12 document-type columns each
   Missing/Requested/Collected, plus a rollup "Done" column) + n8n workflow (schedule trigger →
   filter Missing → Summarize x2 → JS Code node → Gmail **draft**, not auto-send).
2. **In development (the actual target now):** A relational app (tables below) replacing both
   the spreadsheet and the ad hoc Drive folder system. Local v1 is usable. n8n will be
   re-pointed from Sheets to this app's database.

**Decision: build forward on the app, not the spreadsheet.** The spreadsheet workflow stays
running as-is until the app replaces it; don't invest further design effort in the Sheets
version.

## 3. Core Architectural Decisions (the "why")

These principles should govern every design choice below, including ones not yet made. (The
condensed, always-loaded version of these lives in `CLAUDE.md`; this is the full reasoning.)

- **Risk asymmetry is the north star.** A false "Missing" is self-correcting — it triggers
  human review, and the specialist replies "already sent." A false "Collected/Done" is
  dangerous — it silently hides a real compliance gap that nobody ever checks again. Every
  automated status-write must be biased toward under-claiming completion, never over-claiming
  it.
- **Two-key identity model.**
  - **Company/Supplier code** → keys the contact-person lookup (one contact person per
    supplier; multiple emails supported, sent to all).
  - **Project code = Decision Number** → keys which document/row a given payment or upload
    belongs to. One supplier can have multiple projects (multiple decision numbers) over time.
  - Drive folder structure: `projects/[project_code]/` — the folder connects to the project row
    in the database; the database provides company code for contact lookup and full project
    code for row-matching. This avoids fragile filename parsing.
- **Staging over confirmation-bot.** Unverified/ambiguous documents get a `to_verify` status
  (not Missing, not Received) and are held in a separate `verifying` Drive folder, distinct
  from project folders, until a human confirms. After verification: either marked Received, or
  discarded as wrong with no row ever edited. No Telegram/WhatsApp bot needed for v1 — the
  staging area *is* the confirmation mechanism.
- **Codes are auto-populated at creation time, not re-entered per document.** When a Project or
  Payment is created, Project/Payment codes cascade automatically into the Invoices/Receipts
  rows created alongside them. The specialist only fills in *missing document details* on an
  existing row, not free-text identifiers — this removes most of the mis-keying risk, except at
  the initial Project/Payment creation dropdown (see Open Issues).
- **Formalizing an existing checkpoint, not inventing one.** The legacy workflow already used
  Gmail *drafts* (human sends manually), i.e. an informal human-in-the-loop already exists. The
  new system should preserve or upgrade that checkpoint, not remove it in the name of
  "automation."

## 4. Current Schema (as of this session, with fixes applied)

Six tables: **Suppliers, Donors, Decisions, Projects, Payments, Invoices, Receipts.**
(Requirements table not yet built at the time this section was first written — see §5, item 2,
for its resolved status.)

Key fields per table (not exhaustive — see the actual `tableConfigs` in the app code for full
field lists, and `agent.md` for the verified DDL):

- **Suppliers**: `CompanyName`, `Country`, `ContactPerson` (external — who you request documents
  *from*). (`TaxId` dropped 2026-07-19.)
- **Donors**: `DonorCode`, `DonorName`, `Country`, `ContactPerson`.
- **Decisions**: `DecisionNumber`, `DecisionDate`, `Description`, `Attendants`.
- **Projects**: `ProjectCode`, `Subject`, `SupplierId`, `Budget`, `Currency`, `StartDate`,
  `EndDate`, `Status` (Active/Closed/On-Hold/Cancelled — `Completed` dropped 2026-07-19 as
  over-complex for this stage; migrate any live `Completed` rows to `Closed`), `DriveFolderLink`.
- **Payments**: `PaymentCode`, `SupplierId`, `ProjectId`, `DonorId`, `DecisionId`, `Destination`
  (Domestic/International), `Bank`, `Amount`, `Currency`, `Status`
  (Sent/Declared/Closed/Returned/Return-Closed), `PaymentDate`, `DeclarationDate`, `ClosingDate`
  — these last two are included in `columns`, not just `formFields`. (`Payments.ReceiptCode` was
  dropped 2026-07-19 — removed from the DB and from `update_payment()`.)
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
- **Invoices**: `InvoiceCode`, `No`, `SupplierId`, `DonorId`, `ProjectCode`, `Date`, `Amount`,
  `Currency`, `Status`, `Notes`.
- **Receipts**: `ReceiptCode`, `No`, `ProjectCode`, `PaymentCode`, `PaymentDate`, `ReceiptDate`,
  `Amount`, `Currency`, `Status`, `RequiresTranslation`, `AssignedTo`, `Notes`. The
  `Date`-vs-`ReceiptDate` naming mismatch was fixed earlier — see Doc-Drift Log §6, item 1.
  **Domain rule (2026-07-19): a receipt's `Amount`/`Currency` can legitimately differ from its
  payment's (bank cut / commission), so any payment→receipt sync must NEVER overwrite receipt
  money fields — the gap between `Receipt.Amount` and the joined `PaymentAmount` is itself a
  compliance signal.** (Feeds the Phase-4 cascade.)
- **Status (unified)** on Invoices and Receipts — applied in code 2026-07-19 (was only *decided*
  until then; see Doc-Drift Log §6, item 3). Previously two overlapping fields (`Status` with
  staff names baked in, e.g. "Requested Ahmet"; and a separate `Fatura`/`Makbuz` field with
  near-duplicate stages). Now one `Status` enum: `Missing → Requested → Received → Translated →
  Sent → Done`, staff names removed. Two new fields added alongside on both tables:
  `RequiresTranslation` (boolean, default `true`) and `AssignedTo` (text) — the latter closes
  the internal-assignee gap in §5, item 1. `Fatura`/`Makbuz` columns dropped from the DB.

## 4b. Authentication — decisions made 2026-07-19 (mechanics in `agent.md` → Authentication)

Security phase started (parallel to Phase 4). Decisions and their why:

- **Hand-rolled Flask session auth over Flask-Login / Supabase Auth.** Chosen for learning
  value (I own every moving part) and zero new dependencies. Flask-Login is the named future
  upgrade path; Supabase Auth was consciously rejected — it would replace the Accounts table and
  keep auth mechanics a black box.
- **Accounts created manually** (hash from `generate_hash.py` pasted into the Supabase
  dashboard). No self-registration — on an internal compliance tool a signup page is an
  anti-feature. Admin user-management UI + roles (admin/viewer) deferred until there's a real
  second-user need.
- **Default-deny guard, not per-route decorators** — the risk-asymmetry principle applied to
  auth: a forgotten decorator fails *open* (silently unprotected route), a forgotten allowlist
  entry fails *closed* (visible 401).
- **Deployment: local now, VPS soon** → VPS-safe defaults built now (HttpOnly, SameSite=Lax,
  session fixation guard, throttle); the internet-facing items (HTTPS, Secure cookie, gunicorn,
  Flask-Limiter, RLS) are a written checklist in `agent.md`, not vague intentions.
- **Verification status:** see Build Log §7 — "applied in code" is not "verified end-to-end"
  until the Accounts table, `FLASK_SECRET_KEY`, and a seeded account row are confirmed live.
  Per this project's own Doc-Drift Log, don't upgrade the claim without running it.

## 5. Open Issues (unresolved — do not build past these silently)

1. **Internal assignee gap — RESOLVED 2026-07-19.** Merging Status removed the
   "Requested Ahmet" / "Requested Heba" distinction (which internal staff member currently owns
   a document for translation/signing — not `Supplier.ContactPerson`, who is external). Resolved
   by adding an `AssignedTo` text field to Invoices/Receipts: single current holder, no history
   (overwrite loses the prior name — accepted tradeoff).
2. **Requirements table — RESOLVED 2026-07-26.** Design decided 2026-07-19, SQL applied in
   Supabase, and the full frontend edit path (dropdowns → `PUT /api/requirements` → re-fetch)
   verified end-to-end in the browser 2026-07-26 — see Build Log §7 for the exact build. Cascade
   mechanism: **compute the four derived slots in SQL views on read — no stored copy, no DB
   trigger, no app-write cascade, no reconciler.** A slot that is never stored cannot drift. Two
   views: `receipt_compliance` (**payment-grain**; Receipt + Receipt-Translation from
   `Receipts.Status`/`RequiresTranslation`) and `invoice_compliance` (**project-grain**). The
   invoice slot is an **amount-coverage** rule, not a single-Status passthrough (supersedes the
   old locked single-invoice formula, which assumed one invoice): **Collected when Σ(in-hand
   invoices with Status ≥ Received) ≥ Σ(project's non-returned payments)** — every dollar
   actually spent is documented. Denominator is derived from payments, so **no `ActualBudget`
   column** is added. **Ungated/live:** recomputed on every read, so a false "Collected" cannot
   persist — new spend re-opens it. The project-grain invoice-*translation* aggregate rule is
   locked in `CLAUDE.md`/`agent.md`; the human-edited slots' table shape is **long**, split into
   `PaymentRequirements` (3 payment-grain doc types) and `ProjectRequirements` (5 project-grain
   doc types) — this is the authoritative 8-doc-type list, resolving the old wide-vs-long
   contradiction.
2b. **`to_verify` status integration**: confirmed conceptually (§3) but not yet reflected in the
   Requirements table's status enum.
3. **Status pipeline isn't strictly linear across document types — RESOLVED by the four-state
   Requirements model itself**, not by special-casing the six-stage `Status` pipeline. A doc
   type that doesn't apply to a given payment/project is marked `Unnecessary` (a real, human-set
   slot value, not `Missing`); the two computed translation slots go `Unnecessary` automatically
   when `RequiresTranslation` is false. No per-doc-type "skip this stage" logic was needed.
4. **Mis-selection risk at Project/Payment creation.** Auto-populating codes downstream removes
   most mis-keying risk, but the initial dropdown selection of Supplier/Project when creating a
   Payment is still manual and unvalidated. Flagged as a v2 concern, not a blocker for v1.
5. **Schema audit — field-level pass done 2026-07-19.** The other four tables (Suppliers,
   Donors, Decisions, Projects) were run through the three-way, both-directions audit (columns ↔
   formFields ↔ backend dict; see `.claude/rules/schema-audit.md` for the checklist) and all
   four **PASS** — no field mismatch remains. Suppliers was additionally verified end-to-end via
   a live create after the `TaxId` drop; a belt-and-suspenders end-to-end test row for
   Donors/Decisions/Projects is still worth doing but nothing is known broken.
6. **n8n ↔ database integration not yet built.** Plan (agreed, not implemented): n8n stops
   reading Google Sheets on a schedule and instead pulls from the app's database; Drive folder
   creation switches from whatever triggers it today to a webhook fired when a new Project is
   created in the app.
7. **Currency — enforced single-currency-per-project for now (2026-07-29 security review);
   multi-currency-per-project deferred by design, not forgotten.** Today, and for every project
   I've actually run, one project = one currency always. `Currency` is independently entered on
   `Projects`, `Payments`, and `Invoices` with no cross-check — flagged by an external security
   review as a silent-drift risk (nothing stops a payment being logged in a different currency
   than its project, which would then be summed together with same-currency payments in
   `invoice_compliance`'s amount-coverage math, corrupting the Collected/Missing computation
   with no error). **Decided fix, implemented in the current working tree but not yet
   live-verified:** `create_payment`/`update_payment`/`create_invoice`/`update_invoice` in
   `app.py` reject a write whose `Currency` doesn't match its parent `Projects.Currency`.
   The accompanying `sql/phase5_integrity_hardening.sql` also adds fail-closed PostgreSQL
   triggers, so direct writes from the SQL editor, n8n, or a future integration cannot bypass
   that rule. **The Phase 5 migration was applied successfully in Supabase on 2026-08-31, and
   the required Phase 4 view refresh completed successfully ("Success. No rows returned").**
   App-level verification is still required before treating the change as deployment-ready.
   **If a future org needs one project to legitimately hold payments in more than one
   currency**, that single-currency validation is the wrong fix and this open issue needs to be
   reopened as: (a) drop the cross-check, (b) change `invoice_compliance`
   (`sql/phase4_requirements.sql`) to compute `spend_to_document`/`invoiced_in_hand` **grouped by
   currency** instead of one summed total per project, and (c) decide how the `Collected` slot
   reads when some currencies are covered and others aren't (one slot per project can't
   represent that — likely needs to become per-currency itself). Don't build (a)–(c)
   speculatively; this is here so the option is findable, not a queued task.

## 6. Doc-Drift Log

This project has a confirmed pattern of docs claiming something was done when the running code
disagreed. It's why `CLAUDE.md` says to trust nothing here at face value. Add an entry any time
a doc is caught claiming something the code doesn't back up — this log is the evidence, not the
rule; the rule lives in `CLAUDE.md`.

1. **Receipts `Date`/`ReceiptDate` field-name mismatch.** A doc claimed a fix was "applied"
   while the running code still had the mismatch. (Fixed; first confirmed instance.)
2. **`agent.md` silently omitted two real DB columns** (`Fatura`, `Makbuz`) that its own DDL
   should have listed.
3. **2026-07-19 — third confirmed instance.** This document claimed the Invoice/Receipt
   Status-merge was "fix applied" while the running code still had staff-name statuses and the
   `Fatura`/`Makbuz` fields — genuinely applied only on 2026-07-19.

## 7. Build / Migration Log

### Status-merge migration — applied & verified 2026-07-19

1. **DB (Supabase):** six-stage `Status` (plain `text`, no enum type) is what the app now treats
   as valid; `Fatura` (Invoices), `Makbuz` (Receipts), `Payments.ReceiptCode`, and
   `Suppliers.TaxId` **dropped**; `RequiresTranslation` (boolean, default `true`) and
   `AssignedTo` (text) **added** to Invoices + Receipts.
2. **Backend (`app.py`):** all four Invoice/Receipt endpoints write the two new fields, via a
   `_to_bool()` helper that biases an absent/blank `RequiresTranslation` to `true` (a boolean
   column's DEFAULT only fires when the key is *omitted*, so an explicit `None` would defeat it
   — risk asymmetry). `update_payment()` no longer writes `ReceiptCode`; both supplier endpoints
   no longer write `TaxId`. The auto-created Receipt in `create_payment()` sets
   `RequiresTranslation=True` and — bug fixed — uses the numeric `payment_id` for the
   `PaymentCode` BIGINT FK (was writing the text code; see `agent.md` Gotcha #10).
3. **Frontend (`app.js` / `style.css`):** six-stage `Status` options; `Fatura`/`Makbuz` removed;
   `RequiresTranslation` (`true`/`false` select) + `AssignedTo` added; `columns`/`displayNames`
   updated; CSS badges added for the six stages + `On-Hold` + `Return-Closed`. Two fixes surfaced
   during the work: `openModal` populate (`|| ''` → `?? ''`, which had blanked a stored
   `false`/`0` on edit), and `loadLookupData` was initially serialized to stop concurrent-burst
   EAGAIN 500s (`agent.md` #11; resolved in Phase 5 on 2026-08-31).

### Security / auth — applied in code 2026-07-19 (parallel session)

Login/auth built in a separate session alongside Phase 4 (mechanics/DDL in `agent.md` →
Authentication; decision record in §4b above): hand-rolled Flask session auth against a new
`Accounts` table, default-deny `before_request` guard (risk asymmetry: forgetting an allowlist
entry fails closed, not open), werkzeug hashing via `generate_hash.py`, login throttle, CORS
removed, logout button, `apiFetch()` 401 wrapper. **Not verified end-to-end until: (1) the
Accounts table is created in Supabase, (2) `FLASK_SECRET_KEY` is added to `.env` (app now
refuses to start without it), (3) an account row is seeded.** Deferred consciously: Flask-Login,
roles/RBAC, admin user UI, CSRF tokens, Flask-Limiter, HTTPS/Secure cookie — see the VPS-day
checklist in `agent.md`.

### Phase 4 — Requirements table + status cascade — done, verified end-to-end 2026-07-26

The cascade trigger question is resolved — **compute-in-view** (see §5 item 2 and
`sql/phase4_requirements.sql`). SQL is applied in Supabase. Backend edit path
(`GET /api/compliance_report` + `PUT /api/requirements`) is live. The frontend compliance tab's
4-step arc is fully built and live-tested in the browser: (1) nav button +
`loadComplianceReport()`, (2) `renderComplianceReport(data)` driven by the `complianceColumns`
config, (3) `formatComplianceCell` renders the 8 human slots as `<select>` dropdowns
pre-populated with their real stored value (computed slots stay read-only), (4) a delegated
`change` listener on `#tableBody` (in `setupEventListeners()`) builds `{scope, doc_type, status,
owner_id}` from the select's `data-*` attributes + new value, `PUT`s it to `/api/requirements`,
then re-fetches via `loadComplianceReport()` regardless of success/failure — so the UI never
shows an unsaved value as if it were real (risk asymmetry applied to the UI layer itself, not
just the compliance formulas). `owner_id` is explicitly cast with `Number(...)` before sending,
since `dataset` values are always strings and the column is `bigint`.

Two bugs surfaced and fixed during the build, both worth remembering as a *pattern*, not just a
one-off: (a) a `const payload = {...}` block was written as a sibling statement *after* the
`addEventListener` callback's closing `}` instead of inside it, referencing `e` from a scope
where it no longer existed (`ReferenceError: e is not defined`) — same class of bug as an
earlier `data`-out-of-scope mistake in `formatComplianceCell`; (b) the request body used
`method: 'POST'` against a route registered only for `PUT`. Standing domain rule, still
relevant: a receipt's `Amount`/`Currency` can legitimately differ from its payment's (bank cut /
commission) — never overwrite receipt money fields; the `Receipt.Amount` vs joined
`PaymentAmount` gap is itself a compliance signal.

### Phase 5 — integrity hardening — applied 2026-08-31

`sql/phase5_integrity_hardening.sql` ran successfully in Supabase. Its follow-up
`sql/phase4_requirements.sql` view refresh also returned "Success. No rows returned". Database
constraints/triggers are live; the Flask/UI verification described below remains outstanding.

### Phase 5 — Supabase request concurrency — implemented 2026-08-31

The module-level Supabase client was replaced with a Flask request-local client, so concurrent
browser and future n8n requests no longer share client state. `loadLookupData()` now restores
parallel lookup requests. Source checks and normal browser concurrent-load verification completed
2026-08-31; production load verification is still required before relying on it at scale.

**Resume here next:** three small, non-blocking items were deliberately deferred, not forgotten:
(1) revisit **compliance-table content styling** — `.status-collected` and `.status-unnecessary`
CSS badge classes don't exist yet (the four-state Requirements values currently render as bare
`<select>`/text, unlike the six-stage Status badges elsewhere in the app which do have styled
classes); (2) the `Requirment_States` constant name (in `app.js`, near `complianceColumns`) is a
misspelling of "Requirement" — functionally fine (used consistently), flagged only as a
portfolio-quality nit for an eventual rename; (3) **notification-toasts remain behind the
add/edit modal** during validation errors, even after the notification region's `z-index` was
raised above the modal (observed 2026-08-31). Diagnose the stacking context, then likely move
`#notificationRegion` outside `.container` or render validation feedback inside the modal.
Neither blocks Phase 5/6.

### Roadmap

Full walkthrough in `~/.claude/plans/as-my-mentor-first-sorted-sphinx.md`.

- **Phase 5** — n8n ↔ DB re-integration. Backend Supabase concurrency safety was implemented
  and browser-verified 2026-08-31; production load testing remains a later deployment task.
- **Phase 6** — portfolio polish (`requirements.txt` slimming, branding reconciliation,
  `innerHTML` XSS note).

## 8. Working Style — project-specific notes only

The general mentoring approach (guiding questions before solutions, review focused on
reliability/edge cases, not just "does it run") lives in `~/.claude/CLAUDE.md` and applies here
without restating it. The one project-specific sharpening: prefer surfacing tradeoffs and asking
which failure mode is acceptable over silently picking one and generating code — especially for
anything that writes to the Requirements table or triggers a status cascade, given the
risk-asymmetry principle in §3.

## 9. Career Context (brief)

This project is Month 1's flagship portfolio piece in a freelance automation career plan
targeting NGO/M&E/compliance clients (secondary niche: general business ops automation).
Client-facing artifacts (case study writeups, the six-part
problem/process/automation/data-model/human-in-the-loop/out-of-scope spec) are a separate
deliverable from this technical context doc — useful to produce once the Requirements table and
cascade logic are real, not before.
