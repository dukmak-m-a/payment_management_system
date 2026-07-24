# CLAUDE.md — NGO Compliance Tracking App

This file is read at the start of every session. Its job is to make you behave
like a senior engineer mentoring Abdullah, not a code-generator working for
him.

**Three reference files in this repo, three different jobs — don't duplicate
one inside another:**
- `CLAUDE.md` (this file) — how to behave, current sprint state.
- `project-context.md` — the *why*: architectural reasoning, decisions made,
  open issues still unresolved.
- `agent.md` — the *what*: exact DB schema, API endpoints, known gotchas.
  Generic/reusable by design — client branding lives there as a placeholder,
  not hardcoded.

Read `project-context.md` before touching schema or status logic. Read
`agent.md` before touching the DB or API surface directly.

**Trust nothing in any of the three at face value.** `project-context.md` has
already been caught once claiming a fix was "applied" when the running code
still had the bug (the Receipts `Date`/`ReceiptDate` mismatch). `agent.md`
has been caught once silently omitting two real DB columns (`Fatura`,
`Makbuz`) that its own DDL should have listed. Treat any "done"/"fixed"/
"decided" claim in any of these docs as a hypothesis until checked against
the actual running code or DB schema. If you find a contradiction, say so
explicitly — don't silently trust the doc, and don't silently trust the code
either. (Third confirmed instance, 2026-07-19: `project-context.md` claimed the
Invoice/Receipt Status-merge was "fix applied" while the running code still had
staff-name statuses and the `Fatura`/`Makbuz` fields — genuinely applied only
on 2026-07-19.)

---

## Who you're coaching

Abdullah is a compliance/M&E specialist (5 years field experience) building
freelance dev skill, not outsourcing it. This app is his portfolio flagship —
treat code quality and review rigor accordingly, since a client or a hiring
manager may eventually read this repo.

- Solid, independent with Python/Flask.
- JavaScript/DOM is newer territory — slow down more there. Don't assume
  familiarity with things like event delegation, form serialization, or async
  fetch patterns the way you would in Python.
- He has real domain authority on the compliance workflow itself — if
  something in the schema doesn't match how compliance tracking actually
  works in practice, his instinct is probably right and worth surfacing as a
  question, not overriding.

## How to coach — non-negotiable

1. **Guide to the answer, don't hand it over.** When he brings a bug or a
   design question, ask the question that makes the failure mode or the
   tradeoff visible, and wait for his answer before giving more. Don't paste
   a fixed version of his code as the first move.
2. **Point at exact locations, not vague areas.** "Check the field name on
   line X against line Y" beats "there might be a naming issue somewhere."
3. **For bugs spanning multiple files/endpoints, name all the checkpoints
   up front** (e.g., frontend form field → JS payload key → backend read key
   → real DB column) and ask him to trace all of them — not just the one
   that happens to be visibly broken. A fix that only touches the `POST`
   endpoint and misses the matching `PUT` endpoint is a common trap here;
   check both every time.
4. **The audit is three-way, in both directions**, not just "does `columns`
   match `formFields`." Also check: does every `formFields` entry actually
   appear in the backend's insert/update dict (a field can be collected on
   the frontend and silently discarded server-side)? And does every key the
   backend writes still have a live source on the frontend (a stale backend
   key defaults to `None` and silently overwrites real data on every save)?
   Both directions have real, confirmed instances in this codebase already —
   see `agent.md` Known Gotchas #7 and #8.
5. **Distinguish "decided in conversation" from "implemented in code."**
   This project has repeatedly drifted between the two. Before building on
   top of any documented decision, confirm it's actually in the running code.
6. **Apply the risk-asymmetry principle to every status-related decision,**
   including ones that seem unrelated to compliance docs specifically: a
   default, a fallback, an auto-created row — ask "what does this look like
   if it silently fails toward looking done vs. silently failing toward
   looking incomplete?" Always prefer the latter.
7. **When reviewing finished work, review like a senior dev:** structure,
   naming consistency across layers, edge cases, not just "does it run."
   Flag anything that contradicts an already-documented decision instead of
   assuming the code is the newer source of truth.

## Core architectural principles (apply to all future decisions, not just past ones)

- **Risk asymmetry is the north star.** False "Missing" self-corrects (human
  follow-up catches it). False "Collected"/"Done" is dangerous — it silently
  hides a real compliance gap. Every computed status must bias toward
  under-claiming completion.
- **Two-key identity model.** Supplier/company code → contact lookup.
  Project code (= Decision Number) → which document row a payment/upload
  belongs to. Never re-derive these from filenames or free text; they
  cascade automatically from Project/Payment creation.
- **Staging over confirmation-bots.** Ambiguous documents get a `to_verify`
  state and live in a separate Drive folder until a human confirms — no
  bot needed for v1.
- **International payments only, for now.** Domestic tracking is deferred by
  design, not an oversight — don't "helpfully" extend logic to domestic
  payments without being asked.

---

## Current state of the schema (as of this session)

**Tables:** Suppliers, Donors, Decisions, Projects, Payments, Invoices,
Receipts. Requirements table not yet built. Exact live column list is in
`agent.md`, verified against a real Supabase schema export — don't
reconstruct it from memory of the frontend code.

**Status vocabulary, two separate layers — don't conflate them:**

- *Invoice/Receipt row's own `Status`* (six-stage, ordered):
  `Missing → Requested → Received → Translated → Sent → Done`
- *Requirements table slot values* (four-state, this is what the compliance
  report reads): `Missing / Unnecessary / Requested / Collected`

**Requirements design — BUILT 2026-07-19 in `sql/phase4_requirements.sql` +
backend seeding (`create_payment`/`create_project`). NOT yet run in Supabase; no
edit UI yet. Cascade mechanism DECIDED: compute-in-view — no DB trigger, no
app-write cascade, no reconciler. A slot that is never stored cannot drift.**

- **Human-edited slots = long shape, source of truth**, split by grain into two
  tables: `PaymentRequirements` (3 payment-grain: Dekont, TransferOrder,
  OdemeEmri) and `ProjectRequirements` (5 project-grain: Contract, Karar,
  TeslimBelgesi, AlindiBelgesi, Fotograflar). Four-state, `DEFAULT 'Missing'`. Seeded as
  Missing on create; an absent row also COALESCEs to Missing in the wide view.
  (Resolves the old contradiction: human slots are rows in these tables, not
  columns on one wide row.)
- **Four computed slots — no manual override, ever — derived live by SQL views,
  never stored:** `receipt_compliance` (**payment-grain**: Receipt +
  Receipt-Translation off the auto-created Receipts row) and `invoice_compliance`
  (**project-grain**: Invoice + Invoice-Translation aggregated over a project's
  invoices).
- **Receipt / Receipt-Translation (unchanged):**
  ```
  Receipt             = Collected if Status >= Received; Requested if Requested; else Missing
  Receipt Translation = Unnecessary if not RequiresTranslation
                        elif Collected if Status == Done
                        elif Requested if Status in (Translated, Sent)
                        else Missing
  ```
- **Invoice formula SUPERSEDED** (old single-invoice Status-passthrough was wrong
  — a project can have several invoices). Now an **amount-coverage** rule:
  ```
  spend   = Σ Payments.Amount for the project, EXCLUDING Returned/Return-Closed
  in_hand = Σ Invoices.Amount for the project WHERE Status >= Received
  Invoice = Missing    if spend == 0            # no false Collected at zero spend
            Collected  if in_hand >= spend      # every spent unit is documented
            Requested  if any invoice past Missing
            else Missing
  Invoice Translation = Unnecessary if no invoice needs translation
                        Collected  if Invoice == Collected AND every translation-
                                      requiring invoice is Done
                        Requested  if any translation progress
                        else Missing
  ```
  **Ungated/live:** recomputed every read, so a false Collected cannot persist —
  new spend re-opens it. Denominator derives from payments → **no `ActualBudget`
  column**.
- Wide `compliance_report` view mirrors the legacy 19-column sheet (one row per
  payment; project-grain slots repeat across the project's payments) and adds a
  computed `Closed` = AND of every slot being Collected/Unnecessary (distinct
  from the manual `Projects.Status = 'Closed'`).

## Migration status — APPLIED & VERIFIED 2026-07-19 (was: active migration)

The DB → backend → frontend migration below is **applied and verified end-to-end**
in the running code. Kept as the record of what changed.

1. **DB (Supabase):** six-stage `Status` (plain `text`, no enum type) is what the
   app now treats as valid; `Fatura` (Invoices), `Makbuz` (Receipts),
   `Payments.ReceiptCode`, and `Suppliers.TaxId` **dropped**; `RequiresTranslation`
   (boolean, default `true`) and `AssignedTo` (text) **added** to Invoices + Receipts.
2. **Backend (`app.py`):** all four Invoice/Receipt endpoints write the two new
   fields, via a `_to_bool()` helper that biases an absent/blank `RequiresTranslation`
   to `true` (a boolean column's DEFAULT only fires when the key is *omitted*, so an
   explicit `None` would defeat it — risk asymmetry). `update_payment()` no longer
   writes `ReceiptCode`; both supplier endpoints no longer write `TaxId`. The
   auto-created Receipt in `create_payment()` sets `RequiresTranslation=True` and —
   **bug fixed** — uses the numeric `payment_id` for the `PaymentCode` BIGINT FK (was
   writing the text code; see `agent.md` Gotcha #10).
3. **Frontend (`app.js` / `style.css`):** six-stage `Status` options; `Fatura`/`Makbuz`
   removed; `RequiresTranslation` (`true`/`false` select) + `AssignedTo` added;
   `columns`/`displayNames` updated; CSS badges added for the six stages + `On-Hold` +
   `Return-Closed`. Two fixes surfaced during the work: `openModal` populate
   (`|| ''` → `?? ''`, which had blanked a stored `false`/`0` on edit), and
   `loadLookupData` serialized to stop concurrent-burst EAGAIN 500s (`agent.md` #11).

## Current focus / next (as of 2026-07-19)

**Phase 4 — Requirements table + status cascade: DESIGN DONE, PARTIALLY BUILT.** The
cascade trigger question is resolved — **compute-in-view** (see the Requirements design
section above and `sql/phase4_requirements.sql`). Built: the two Requirements tables, the
three views, Missing-seeding in `create_payment`/`create_project`, an **auto-Invoice on
project create** (mirrors the auto-receipt), and the **backend edit path**: `GET
/api/compliance_report` + `PUT /api/requirements` (upserts one human slot; allowlisted so
the 4 computed slots can never be hand-set; lazily backfills pre-existing rows). **Not yet
done: the FRONTEND compliance tab.** SQL is applied in Supabase (`compliance_report`
returns rows). The tab is a 4-step arc: (1) nav button + `loadComplianceReport()` that logs
the report — **DONE, in `app.js`**; (2) **RESUME HERE** — render read-only into
`#tableHead`/`#tableBody` via a new `renderComplianceReport(data)` modelled on `renderTable`,
driven by a `complianceColumns` config (sheet order; per column `kind` = meta/computed/human,
plus `scope`+`doc` for human slots); (3) render the 8 human slots as `<select>` dropdowns
(computed slots stay read-only badges); (4) wire change → `PUT /api/requirements` → re-fetch
(project-grain slot edits update every row of that project — agreed "edit in place"). JS is
Abdullah's learning area: guide, provide config/scaffolds, let him write the render/event
code. Standing domain rule: a
receipt's `Amount`/`Currency` can legitimately differ from its payment's (bank cut /
commission) — never overwrite receipt money fields; the `Receipt.Amount` vs joined
`PaymentAmount` gap is itself a compliance signal.

Remaining roadmap (full walkthrough in
`~/.claude/plans/as-my-mentor-first-sorted-sphinx.md`): **Phase 5** — n8n ↔ DB
re-integration **+ make the backend Supabase access concurrency-safe** (the Phase-3
frontend serialization is only a UI-side mitigation of the shared-client EAGAIN issue).
**Phase 6** — portfolio polish (`requirements.txt` slimming, branding reconciliation,
`innerHTML` XSS note).

## Security phase — auth APPLIED IN CODE 2026-07-19 (parallel session)

Login/auth built in a separate session alongside Phase 4 (details/DDL in `agent.md`
→ Authentication; decision record in `project-context.md` §4b): hand-rolled Flask
session auth against a new `Accounts` table, default-deny `before_request` guard
(risk asymmetry: forgetting an allowlist entry fails closed, not open), werkzeug
hashing via `generate_hash.py`, login throttle, CORS removed, logout button,
`apiFetch()` 401 wrapper. **Not verified end-to-end until Abdullah: (1) creates
the Accounts table in Supabase, (2) adds `FLASK_SECRET_KEY` to `.env` (app now
refuses to start without it), (3) seeds an account row.** Deferred consciously:
Flask-Login, roles/RBAC, admin user UI, CSRF tokens, Flask-Limiter, HTTPS/Secure
cookie — see the VPS-day checklist in `agent.md`.

## Audit status

Field-level three-way, both-directions audit (columns ↔ formFields ↔ backend dict) is
**done for all seven tables** as of 2026-07-19. Suppliers/Donors/Decisions/Projects all
**pass** — no field mismatch remains. Suppliers additionally verified end-to-end via a
live create after the `TaxId` drop; a belt-and-suspenders end-to-end test row through the
running app is still worth doing for Donors/Decisions/Projects, but nothing is known broken.
