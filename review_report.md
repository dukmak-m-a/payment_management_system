# Code Review: NGO Compliance Tracking App (full-app review, 2026-07-26)

Reviewed under `CODE_REVIEWER.md`. Scope: entire working tree at commit `caa6407` +
uncommitted changes to `static/app.js` and `static/style.css`.

Files read in full: `app.py` (730 L), `static/app.js` (883 L), `static/style.css` (943 L),
`templates/index.html`, `templates/login.html`, `sql/phase4_requirements.sql`,
`generate_hash.py`, `requirements.txt`, `README.md`, `.gitignore`, plus `agent.md` /
`project-context.md` / `CLAUDE.md` as claimed-state references (verified against code, not
trusted).

---

### Summary

**Verdict: go-with-fixes — but three of the fixes are non-negotiable before this holds real
compliance data.**

The architecture is genuinely good, and better than most code at this stage: compute-in-view
instead of a stored cascade is the right call and eliminates a whole class of drift bugs;
default-deny auth is the right shape; the risk-asymmetry principle is applied consistently and
deliberately in the places the author thought about. The problems are almost all in the places
where that principle *silently stops holding* — not because the logic is wrong, but because
SQL's three-valued logic and unconstrained columns route around it.

Three blockers: (1) the app currently binds `0.0.0.0` with `debug=True` while holding a
Supabase **service_role** key, which is remote code execution → total database control on any
network the machine sits on; (2) `NULL` values in `Payments.Status`, `Payments.Amount`, and
`Invoices.RequiresTranslation` each produce a **false `Collected`/`Closed`** in the compliance
views — the exact failure mode the whole design exists to prevent; (3) the amount-coverage rule
sums mixed currencies, so 1,000 USD of invoices "covers" 1,000,000 TRY of payments.

Below that: a duplicated-receipt path that double-renders compliance rows, an auto-created
placeholder invoice that permanently pins `Closed` to `No`, stored XSS, PUT endpoints that null
every omitted column, and a repo that does not install from a clean clone. None of these are
hard to fix; several are one-line DDL changes.

The recurring theme worth internalizing: **the risk-asymmetry guarantee is only as strong as the
DB constraints under it.** Right now it lives in Python defaults and view `CASE` ordering, both
of which `NULL` walks straight past.

---

### What was checked

| § | Section | Why |
|---|---|---|
| A | Architecture & Organization | Full-app review; three layers + views |
| B | Correctness & Logic | The compliance formulas are the product |
| C | Security | Auth, secrets, injection, session handling all in scope |
| D | Performance | New views + unindexed joins + no pagination |
| E | Accessibility | User-facing app, WCAG AA baseline |
| F | Responsive & Cross-Browser | Mobile breakpoints exist and were checked |
| G | Testing | Zero tests present; non-trivial money logic |
| H | API Design | 16 endpoints, about to be consumed by n8n |
| I | Database & Data Integrity | Constraints are where the blockers live |
| J | Dependencies & Supply Chain | `requirements.txt` is a pip-freeze |
| K | Error Handling & Observability | `str(e)` to clients, no audit trail |
| M | i18n / l10n | Bilingual TR/EN UI, TRY currency |
| N | DevOps / Config | `.env`, secrets, debug flag |
| O | Documentation | Portfolio repo; README is the front door |

**Not checked:** §L (SEO/metadata) — internal auth-gated tool, not indexable. Runtime browser
testing and live DB queries were not performed; every finding below is derived from reading the
code and the verified schema in `agent.md`. Findings marked *(unverified at runtime)* are the
ones you should reproduce before fixing.

---

## Findings

---

### 🔴 Blocker — Debug server on `0.0.0.0` + service_role key = full database compromise

- **Location:** `app.py:730` (`app.run(debug=True, host='0.0.0.0', port=5000)`), `app.py:45-48`, `.env`
- **Issue:** The app binds every network interface with the Werkzeug interactive debugger
  enabled. I checked the key in `.env` (metadata only, no secret printed): its JWT `role` claim
  is **`service_role`** — the key that bypasses every Row Level Security policy in the project.
  Anyone who can reach port 5000 and trigger any unhandled exception gets an interactive Python
  console; from that console, `os.environ['SUPABASE_KEY']` is one line away. Supabase's REST
  endpoint is public, so that key is usable from anywhere on the internet, forever, with no
  further access to your machine.
- **Why it matters:** This is not "hardening for VPS day." It is live today on whatever LAN,
  café Wi-Fi, or hotspot this laptop joins. The debugger PIN is derived from predictable machine
  attributes and is not a security control. The blast radius is not "someone sees the app" — it
  is read/write/drop on the entire production database, including `Accounts`.
- **This also answers the open question in `agent.md` → VPS-day checklist #6** ("Check which
  Supabase key `.env` holds"). It is service_role. That item can be marked resolved-and-urgent.
- **Fix:** Three changes, in order of urgency:
  1. `app.run(debug=True, host='127.0.0.1', port=5000)` — today. Loopback only until you are
     behind a reverse proxy. If you need LAN access for testing, use `debug=False` and accept
     losing the reloader.
  2. Rotate the Supabase key now (it has been in a `.env` on a `0.0.0.0`-bound debug server).
     `.env` is correctly gitignored and never committed — I verified `git log --all -- .env` is
     empty — so this is precaution, not confirmed exposure.
  3. Decide deliberately whether the server should hold service_role at all. It legitimately
     needs to bypass RLS *if* all authorization lives in Flask, which is your current design.
     That is defensible — but then enable RLS with a deny-all default on every table so that a
     leaked *anon* key is worthless, and never expose the anon key path to any of these tables.
- **Related, do not do:** `sql/phase4_requirements.sql:202` suggests
  `GRANT SELECT ON public.compliance_report TO anon, authenticated;` for Phase 5. The `anon`
  role's key is public by design (it ships in browsers). That grant publishes your entire
  compliance report — every payment amount, supplier, and gap — to anyone who has ever seen the
  anon key. Have n8n authenticate with a dedicated role or call your Flask API instead.

---

### 🔴 Blocker — `NULL` defeats risk asymmetry in three places, each producing a false "done"

- **Location:** `sql/phase4_requirements.sql:103-105`, `:107-109`, `:115-117`;
  schema in `agent.md` (Payments/Invoices DDL)
- **Issue:** Three nullable columns feed `CASE`/`WHERE` expressions whose *false* branch is the
  optimistic one. SQL's three-valued logic means `NULL` does not take the pessimistic path — it
  silently takes the other one.

  **(a) `NULL Payments.Status` removes a payment from the spend denominator.**
  ```sql
  WHERE pay."ProjectId" = proj.id
    AND pay."Status" NOT IN ('Returned','Return-Closed')   -- line 105
  ```
  `NULL NOT IN (...)` evaluates to `NULL`, not `TRUE`, so the row is filtered out. `Payments.Status`
  is nullable, and `create_payment()` (`app.py:307`) writes `data.get("Status")` with no default
  and no validation. A payment created through the API without a `Status` — exactly what n8n will
  do in Phase 5 — vanishes from `spend_to_document`. Less spend to document ⇒ the coverage test
  `invoiced_in_hand >= spend_to_document` passes on less evidence ⇒ **`invoice = 'Collected'`
  while real money is undocumented.**

  **(b) `NULL Payments.Amount` does the same, quietly.** `SUM()` skips `NULL`s. `Amount` is
  nullable and `create_payment()` writes `data.get("Amount")`. A payment with no amount counts
  as zero spend.

  **(c) `NULL Invoices.RequiresTranslation` flips Fatura to `Unnecessary`.**
  ```sql
  EXISTS (... AND inv."RequiresTranslation" = true) AS any_needs_translation  -- line 117
  ...
  WHEN NOT agg.any_needs_translation THEN 'Unnecessary'                       -- line 92
  ```
  `NULL = true` is `NULL`, so a NULL-translation invoice is not counted as needing translation.
  If a project's invoices all have `NULL`, `any_needs_translation` is false and `invoice_translation`
  reads `'Unnecessary'`. And `compliance_report`'s `closed` treats `'Unnecessary'` as satisfied
  (`:188`) — so this contributes directly to a **false `Closed = 'Yes'`**. The column has
  `DEFAULT true` and `_to_bool()` (`app.py:55-66`) correctly biases toward `true`, but a DEFAULT
  only fires when the key is *omitted*; any direct insert sending an explicit `null` writes NULL.
- **Why it matters:** These are not edge cases in an unrelated corner — they are the three
  inputs to the compliance engine, and every one of them fails toward "looks done." `CLAUDE.md`'s
  core principle says a false `Collected` "silently hides a real compliance gap." All three paths
  do exactly that, and none of them are visible to the person reading the report.
- **Fix:** Fix it in the DB, once, where every writer (Flask, n8n, the Supabase dashboard, a
  future script) routes through — not in `app.py`, which only covers one caller:
  ```sql
  ALTER TABLE public."Payments"
    ALTER COLUMN "Status" SET NOT NULL,
    ALTER COLUMN "Amount" SET NOT NULL,
    ADD CONSTRAINT "Payments_Status_check"
      CHECK ("Status" IN ('Sent','Declared','Closed','Returned','Return-Closed'));

  ALTER TABLE public."Invoices" ALTER COLUMN "RequiresTranslation" SET NOT NULL;
  ALTER TABLE public."Receipts" ALTER COLUMN "RequiresTranslation" SET NOT NULL;
  ```
  Then belt-and-braces the views so a future nullable column cannot re-open the hole —
  `COALESCE(pay."Status",'')` at `:105`, `COALESCE(inv."RequiresTranslation", true)` at `:117`.
  Backfill existing NULLs first or the `ALTER` will fail (which is itself a useful audit: run
  `SELECT count(*) FROM "Payments" WHERE "Status" IS NULL OR "Amount" IS NULL;` first).
- **General principle worth writing into `CLAUDE.md`:** *any* column a compliance view branches
  on must be `NOT NULL`. Add that to the audit checklist alongside the existing three-way
  field audit.

---

### 🔴 Blocker — Amount coverage sums mixed currencies

- **Location:** `sql/phase4_requirements.sql:103-109`
- **Issue:** Both sides of the coverage test are bare `SUM("Amount")` with no currency
  predicate and no conversion:
  ```sql
  SUM(pay."Amount") ... AS spend_to_document
  SUM(inv."Amount") ... AS invoiced_in_hand
  ...
  WHEN agg.invoiced_in_hand >= agg.spend_to_document THEN 'Collected'
  ```
  `Payments.Currency` and `Invoices.Currency` are independent free-text columns; the UI offers
  TRY / USD / EUR on both (`app.js:55-56`, `:123`). A project paid 1,000,000 TRY and invoiced
  1,000 USD computes `1000 >= 1000000` → false → `Requested`; the reverse (paid 1,000 USD,
  invoiced 1,000,000 TRY) computes `1000000 >= 1000` → **`Collected`**.
- **Why it matters:** Same category as the finding above but arrives through a completely
  ordinary data path — a Turkish supplier invoicing in TRY against a USD donor disbursement is
  the normal case for this organization, not an anomaly. Nothing in the UI, the API, or the
  schema prevents it, and the resulting `Collected` is indistinguishable from a real one.
- **Fix:** You have real domain authority here and should pick, but the options are:
  1. **Per-currency coverage (recommended).** Require coverage independently for every currency
     the project has spend in; the slot is `Collected` only if every currency is covered.
     Roughly: `NOT EXISTS (SELECT 1 FROM currency_totals WHERE invoiced < spent)`. Correct with
     no FX data, no rates to maintain, and it fails toward `Requested` on any mismatch.
  2. **Constrain at the source.** Enforce that an invoice's currency matches its project's
     payments' currency, and reject the rest at the API boundary. Simpler, but wrong the first
     time a real project legitimately mixes currencies.
  3. FX conversion with a rate table — the most "correct" and by far the most machinery. Not
     worth it for v1.
- Whichever you choose, add the intermediate `spend_to_document` / `invoiced_in_hand` columns to
  the compliance UI (the view already exposes them, `:81-82`) so a human can see *why* a slot
  says what it says. A coverage rule you cannot eyeball is a coverage rule you cannot audit.

---

### 🟠 High — A second receipt on one payment duplicates that payment's row in the compliance report

- **Location:** `sql/phase4_requirements.sql:66-67`; `Receipts` DDL in `agent.md` (no UNIQUE on
  `PaymentCode`); reachable via `app.js` Receipts tab → Add New
- **Issue:** `receipt_compliance` is `Payments LEFT JOIN Receipts ON r."PaymentCode" = p.id`.
  Nothing constrains a payment to one receipt: `create_payment()` auto-creates one
  (`app.py:324-332`), and the Receipts tab lets anyone create another for the same payment
  (`app.js:156`, `lookup: 'payments'`). Two receipts ⇒ two rows out of `receipt_compliance` for
  that `payment_id` ⇒ `compliance_report` emits **two rows for that payment** (`:164`).
- **Why it matters:** Two distinct harms. First, the report double-counts — a reader scanning
  for gaps sees the payment twice. Second and worse: if the officer's manually-added receipt is
  `Done` and the auto-created placeholder is still `Missing`, one of those two rows shows
  `receipt = 'Collected'`. Scanning down the report, that payment looks satisfied. The other row
  says otherwise, but nothing draws the eye to the contradiction. This is a false `Collected`
  that the risk-asymmetry design never anticipated, because it arrives through row multiplicity
  rather than through a status value.
  This is *likely*, not theoretical: the auto-created receipt has no code, no date, and no
  marking that distinguishes it from an empty row, so an officer who doesn't know it exists will
  reasonably create "the" receipt themselves.
- **Fix:** Decide whether one payment can have multiple receipts.
  - **If no (recommended, matches the current design):** `ALTER TABLE public."Receipts" ADD
    CONSTRAINT "Receipts_PaymentCode_key" UNIQUE ("PaymentCode");` The DB now makes the second
    receipt impossible instead of the view papering over it. Existing duplicates must be merged
    first.
  - **If yes:** aggregate in `receipt_compliance` instead of joining — `GROUP BY p.id` with a
    weakest-link rule (`MIN` over an explicit status ordering, not alphabetical `MAX`) so
    multiple receipts collapse to one row taking the *least* complete status.
- **Related:** make the auto-created rows identifiable. A `Notes = 'auto-created placeholder'`
  on the receipt and invoice inserts (`app.py:271`, `:324`) costs nothing and makes both this
  bug and the next one visible to the officer instead of invisible.

---

### 🟠 High — The auto-created placeholder invoice permanently pins `fatura` and `Closed` to incomplete

- **Location:** `app.py:271-277` (auto-invoice on project create) ×
  `sql/phase4_requirements.sql:118-121` (`all_translations_done`)
- **Issue:** `create_project()` inserts a placeholder invoice with `Status='Missing'` and
  `RequiresTranslation=True`. The translation aggregate is weakest-link:
  ```sql
  NOT EXISTS (SELECT 1 FROM "Invoices" inv
              WHERE inv."ProjectCode" = proj."ProjectCode"
                AND inv."RequiresTranslation" = true
                AND inv."Status" IS DISTINCT FROM 'Done') AS all_translations_done
  ```
  The placeholder is `RequiresTranslation = true` and `Status = 'Missing'`, so it permanently
  satisfies the inner `EXISTS`. `all_translations_done` is therefore **false forever** unless
  someone sets the placeholder itself to `Done`. `invoice_translation` can never reach
  `'Collected'` (`:95`), and because `closed` ANDs every slot (`:188`), **`Closed` can never be
  `'Yes'` for that project.**
- **Why it matters:** It only bites when the officer adds a *new* invoice rather than editing
  the placeholder — which is precisely the case the amount-coverage redesign was built for
  ("a project can have several invoices", `CLAUDE.md`). So the design's motivating scenario is
  the one that breaks its headline output column. The direction is safe (under-claiming), but a
  `Closed` column that is structurally always `No` is a column nobody reads, and an unread safety
  signal is not a safety signal.
- **Fix:** Pick one:
  1. **Don't auto-create the invoice.** The receipt auto-create earns its keep (a payment always
     needs exactly one receipt); an invoice is project-grain and count-unknown, so the mirror is
     not actually symmetric. The view already handles zero invoices correctly — `spend > 0` with
     no invoices yields `'Missing'` (`:88`), which is the honest answer. This is the smallest
     diff and removes the zombie class entirely.
  2. Keep it, but exclude placeholders from the aggregates: mark them (`Notes`, or an
     `IsPlaceholder boolean`) and add `AND NOT inv."IsPlaceholder"` to the four subqueries at
     `:111-125`. More machinery, and the placeholder still pollutes the Invoices tab.
- **Verify after fixing:** create a project, add two real invoices, mark both `Done`, and
  confirm `fatura = 'Collected'` and `closed = 'Yes'` once the other slots are satisfied.
  *(unverified at runtime — reasoned from the SQL)*

---

### 🟠 High — Stored XSS via `innerHTML`, plus `javascript:` URLs in the Drive-link column

- **Location:** `app.js:572-581` (`renderTable`), `:584-617` (`formatCell`), `:610-614`
  (`DriveFolderLink`), `:790-802` (`viewDetails`), `:406-410` + `:413-446` (compliance render),
  `:667-693` (lookup `<option>` labels)
- **Issue:** Every render path is string-concatenated into `.innerHTML` with raw database values
  and no escaping. `formatCell` returns `value` untouched at `:616`. Concretely:
  - A supplier saved as `<img src=x onerror="fetch('/api/suppliers/1',{method:'DELETE'})">`
    executes on every page that lists suppliers. (`<script>` tags do not run via `innerHTML`;
    `<img onerror>` does — this is the standard bypass.)
  - `DriveFolderLink` is interpolated straight into `href` (`:611`) with no scheme check, so
    `javascript:fetch(...)` is a working payload one click away.
  - `title="Open Drive Folder"` and every `data-*` attribute in `formatComplianceCell` (`:433`)
    are attribute-injection points for a value containing `"`.
- **Why it matters:** Today the trust boundary is "authenticated staff", which caps this at
  insider/self-inflicted — real but bounded. **Phase 5 moves that boundary.** The n8n pipeline
  is designed to write document-derived text (supplier names, notes, codes extracted from PDFs)
  into these same fields. At that point an attacker who can get a document into the intake
  folder gets JavaScript execution in a logged-in officer's browser. `HttpOnly` protects the
  cookie itself but not the session: injected JS simply calls your API with the user's
  credentials. `agent.md` already ranks this "higher priority now" — it should be fixed *before*
  Phase 5 wires up the intake, not in Phase 6 after.
- **Fix:** One helper, applied at the boundary — do not hand-escape at 30 call sites:
  ```js
  const esc = s => String(s).replace(/[&<>"']/g, c =>
      ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  ```
  Wrap every interpolated *data* value (not your own markup) in `esc()`: `formatCell`'s fallthrough
  return, the badge/anchor/`data-*` builders, the `<option>` labels and values, and the
  `displayNames` fallbacks. For `DriveFolderLink`, also validate the scheme before rendering the
  anchor at all — allow `http:`/`https:` and render plain text otherwise. `new URL(value)` in a
  `try` is the lazy way to do both parse and validate.
  The thorough alternative is `textContent` + `createElement`, which is immune by construction
  but a much larger rewrite of the render layer; the escape helper buys ~95% of the safety for
  ~10 lines. Take the helper now, and note the ceiling.

---

### 🟠 High — Every `PUT` is a full-row overwrite: any omitted field becomes `NULL`

- **Location:** `app.py:398-531` — all seven update endpoints
- **Issue:** Each `update_*` builds a complete column dict from `data.get(...)` and sends it to
  `.update()`. Keys absent from the request body become Python `None` → SQL `NULL`. It works
  today only because `handleFormSubmit` (`app.js:726-731`) always serializes every field in
  `formFields`. Nothing in the API contract says so, and nothing enforces it.
- **Why it matters:** This is the *same shape* as the `Payments.ReceiptCode` bug documented in
  `agent.md` gotcha #8 — a key the backend writes with no live source silently nulled real data
  on every save. That instance was fixed; the mechanism that produced it is still standing and
  is now aimed at Phase 5. The natural way to write an n8n node is
  `PUT /api/receipts/42 {"Status": "Received"}` — which will null `ProjectCode`, `PaymentCode`,
  `PaymentDate`, `ReceiptCode`, `No`, `ReceiptDate`, `Amount`, `Currency`, `AssignedTo`, and
  `Notes` in one request, and set `RequiresTranslation` back to `true` via `_to_bool`'s default.
  Silent, unrecoverable data loss on a route that looks like it did the right thing (it returns
  `{"success": true}`).
  Note the internal inconsistency: `/api/requirements` (`app.py:557`) is a *partial* upsert. Two
  update semantics in one API is a trap for whoever integrates next — including future you.
- **Fix:** Make the entity `PUT`s write only what was sent. One shared helper, used by all seven:
  ```python
  def _patch(data, allowed):
      """Only columns actually present in the request body get written."""
      return {k: data[k] for k in allowed if k in data}
  ```
  Then `supabase.table("Receipts").update(_patch(data, RECEIPT_COLS)).eq("id", id)`, with
  `RECEIPT_COLS` as the per-table allowlist (which also gives you a single named place to
  reconcile against `formFields` during the three-way audit — currently that list is implicit in
  the dict literal). Guard the empty-patch case: `if not patch: return jsonify(...), 400`, since
  a PostgREST update with no columns is not what anyone meant. `RequiresTranslation` keeps its
  `_to_bool` treatment when present, and is simply not written when absent — which is the
  correct behavior and lets the DB default do its job.
  If you prefer strict REST semantics, the alternative is to keep `PUT` as full-replace and add
  `PATCH` for partials — more surface, same outcome. Given one frontend and one automation
  client, the patch-only route is the smaller correct thing.

---

### 🟠 High — Nothing validates `Amount`, at any layer

- **Location:** `app.js:54` / `:86` / `:122` / `:159` (`type: 'number'`, no `min`);
  `app.py:305`, `:359`, `:382` (`data.get("Amount")`, no check); `agent.md` DDL (no `CHECK`)
- **Issue:** A negative amount is accepted by the browser (`<input type="number">` without `min`
  permits `-`), by Flask, and by Postgres. It then flows into `spend_to_document`.
- **Why it matters:** A single mistyped `-` in a payment amount *reduces* the project's spend
  denominator, which lowers the bar the invoices must clear. Payments of 5,000 and −1,000 with
  4,000 of invoices in hand computes `4000 >= 4000` → **`Collected`**, while 5,000 actually went
  out the door. One keystroke, no warning, silently-hidden compliance gap. The same absence lets
  a zero-amount payment through, which is the `spend == 0 → 'Missing'` path and at least fails
  safe.
- **Fix:** All three layers, because each catches a different caller:
  ```sql
  ALTER TABLE public."Payments" ADD CONSTRAINT "Payments_Amount_check" CHECK ("Amount" >= 0);
  ALTER TABLE public."Invoices" ADD CONSTRAINT "Invoices_Amount_check" CHECK ("Amount" >= 0);
  ALTER TABLE public."Receipts" ADD CONSTRAINT "Receipts_Amount_check" CHECK ("Amount" >= 0);
  ALTER TABLE public."Projects" ADD CONSTRAINT "Projects_Budget_check" CHECK ("Budget" >= 0);
  ```
  The DB constraint is the one that actually holds — it covers n8n, the Supabase dashboard, and
  every future client. Add `min: '0'` to the numeric `formFields` entries and have
  `renderFormField` (`app.js:703-706`) emit it, so the officer gets an instant browser-level
  message instead of a 400 with a Postgres constraint name in it.
- **While you're there:** there is no `EndDate >= StartDate` check on Projects and no
  `ClosingDate >= PaymentDate` check on Payments either. Same one-line `CHECK` treatment.

---

### 🟠 High — The Compliance tab breaks three shared toolbar controls

- **Location:** `app.js:850-865` (`handleSearch`), `:623-657` (`openModal`), `:465-481`
  (`openColumnSettings`); `templates/index.html:48-60`
- **Issue:** There is no `tableConfigs.compliance` entry (correctly — compliance uses
  `complianceColumns`), but three handlers reach for `tableConfigs[currentTable]` unconditionally
  while the compliance tab is active:
  - `handleSearch:852` → `config.columns.some(...)` on `undefined` → `TypeError`. Typing in the
    search box on the Compliance tab throws on every keystroke and filters nothing.
  - `openModal:629` → `tableConfigs[currentTable].name` → `TypeError`. "Add New" does nothing.
  - `openColumnSettings:466` → same. "Columns" does nothing.

  All three throw inside event handlers with no `catch`, so the user sees no error at all —
  the button is simply inert. *(unverified at runtime; reasoned from the code paths)*
- **Why it matters:** Three of the four controls in the action bar are visibly present and
  silently dead on the tab that is the app's headline feature. From the user's side this reads
  as "the app is broken," and there is no feedback to distinguish it from a slow network. For a
  portfolio repo, it is also the first thing a reviewer will click.
- **Fix:** The lazy correct fix is one guard plus one class, not three patches. In the nav
  handler (`app.js:272-280`), toggle a `body.compliance-mode` class, and in CSS hide
  `#addNewBtn` and `#columnSettingsBtn` under it — the controls genuinely do not apply to a
  computed read-only report, so hiding beats disabling. Then make search work rather than
  crash: have `loadComplianceReport` store its rows (in `currentData` or a dedicated
  `complianceData`) and branch `handleSearch` on `currentTable === 'compliance'` to filter
  `complianceColumns.map(c => c.key)` and re-render via `renderComplianceReport`. That is ~6
  lines and turns a crash into the feature you'd have wanted anyway.
- **Related bug in the same area:** `loadComplianceReport` never assigns `currentData`, so after
  visiting Compliance the global still holds the *previous* tab's rows. Nothing reads it before
  the next `loadData()` overwrites it, so it is latent today — but it is a live footgun for the
  next feature that touches `currentData`. Set it (or explicitly null it) when the compliance
  view renders.

---

### 🟠 High — The app is silent on success and blocking on failure

- **Location:** `app.js:876-883` (`showNotification`), `:298-313` (compliance change handler)
- **Issue:** `showNotification` only surfaces `type === 'error'`, via a blocking `alert()`.
  Every success path — "Record created successfully" (`:748`), "Record deleted successfully"
  (`:832`), "Column order saved" (`:533`) — calls `console.log` and nothing else. The user gets
  no confirmation that a save landed.
  In the compliance handler the gap is sharper: the response is parsed into `result` (`:310`)
  and then **never read**. A `PUT /api/requirements` that returns `{"success": false}` produces
  no message; the subsequent `loadComplianceReport()` re-renders the true stored value, so the
  dropdown silently snaps back. From the officer's chair, changing a status to `Collected` and
  watching it revert with no explanation is indistinguishable from a UI glitch — so the natural
  response is to try again, and then to assume it worked.
- **Why it matters:** The re-fetch-regardless design is right (documented in `CLAUDE.md` as risk
  asymmetry applied to the UI, and it is), but "never show an unsaved value as real" and "tell
  the user the save failed" are different requirements. You have implemented the first and
  skipped the second, and the second is what turns a silent revert into a bug report. `alert()`
  for errors also blocks the event loop and cannot be styled or stacked.
- **Fix:** Make `showNotification` render a real toast — a fixed-position `div`, a CSS class per
  type, `setTimeout` to remove. ~15 lines of JS + ~15 of CSS, no dependency, and you already
  have the call sites wired up for it. Then in the compliance handler, act on the parsed result:
  `if (!result.success) showNotification('Could not save: ' + result.error, 'error');` before
  the re-fetch. Give the toast `role="status"` (and `role="alert"` for errors) so it is
  announced to screen readers — that closes the §E `aria-live` item at the same time.

---

### 🟠 High — The repo does not install or run from a clean clone

- **Location:** `requirements.txt`, `README.md`
- **Issue:** Two separate problems, one symptom.
  1. `requirements.txt` is a full `pip freeze` of your entire development environment: 130
     packages including `matplotlib`, `seaborn`, `pandas`, `playwright`, `PySimpleGUI`,
     `PyMuPDF`, `pyiceberg`, `ipykernel`, `reportlab`, and `Flask-SQLAlchemy` — none of which
     this app imports. It also pins `flask-cors==6.0.2`, deliberately removed from the code on
     2026-07-19, and **`pywin32==306` + `win32_setctime==1.2.0`, which are Windows-only and will
     hard-fail `pip install -r requirements.txt` on Linux and macOS** — including the Fedora
     machine this is being built on.
  2. `README.md` documents a **different application**: a SQLite backend, a
     `create_database.py` setup step that does not exist, `Suppliers.TaxId` and
     `Projects.DonorId` (both dropped/never existed), a `Payments.Kind` column, five tables
     instead of nine, and no mention of Supabase, `SUPABASE_URL`/`SUPABASE_KEY`, the login
     flow, or `FLASK_SECRET_KEY` — without which the app now refuses to start (`app.py:28`).
     Following the README start-to-finish produces a non-working app and a confusing error.
- **Why it matters:** `CLAUDE.md` states this repo is the portfolio flagship and that "a client
  or a hiring manager may eventually read this repo." The two files they will open first are
  `README.md` and `requirements.txt`, and both currently say the project is something it isn't.
  This is the single highest-leverage fix in this review relative to effort: the app itself is
  substantially better than its front door suggests.
- **Fix:** `requirements.txt` is four lines. That is the whole real dependency set:
  ```
  Flask==3.0.0
  python-dotenv==1.0.0
  supabase==2.29.0
  Werkzeug==3.1.3
  ```
  (Werkzeug and Jinja2 arrive with Flask; pinning Werkzeug explicitly is worth it since you use
  `werkzeug.security` directly.) Verify in a throwaway venv:
  `python -m venv /tmp/v && /tmp/v/bin/pip install -r requirements.txt && /tmp/v/bin/python -c "import app"`.
  For the README, cover: what the app is, the real stack, the three required env vars, DB setup
  (`sql/phase4_requirements.sql` + the DDL in `agent.md`), creating the first account with
  `generate_hash.py`, how to run, and a short architecture paragraph. The compute-in-view
  compliance design and the risk-asymmetry principle are genuinely the most interesting things
  here — a hiring manager who reads about them will read the code differently. `agent.md` and
  `project-context.md` already contain the material; the README just needs to point at it.
  Also fix `agent.md`'s own stale copies: it lists `flask-cors` in the tech-stack table and in
  `pip install Flask flask-cors supabase`, both wrong since the CORS removal.

---

### 🟠 High — No audit trail on compliance status changes

- **Location:** `app.py:557-587` (`upsert_requirement`); `PaymentRequirements` /
  `ProjectRequirements` DDL in `sql/phase4_requirements.sql:24-41`
- **Issue:** The upsert writes `{owner_id, DocType, Status}` and nothing else. Neither table has
  `UpdatedBy` or `UpdatedAt`, and no history row is written — even though `session['user_id']`
  is right there in scope and an `Accounts` table already exists. A status that moved from
  `Missing` to `Collected` is indistinguishable from one that was always `Collected`, and there
  is no record of who moved it or when.
- **Why it matters:** This is a compliance tool for donor-funded work. "Who marked this
  collected, and when?" is the first question in any donor audit or internal dispute, and it is
  the question this system is best positioned to answer and currently cannot. It also removes
  the only realistic defence against the false-`Collected` failure modes above: with a trail,
  an anomaly is investigable after the fact; without one, a wrong `Collected` is permanent and
  anonymous. The domain expertise is yours, but from a reviewer's seat this is a functional gap,
  not a nice-to-have.
- **Fix:** Cheapest version that actually helps, two columns and one line:
  ```sql
  ALTER TABLE public."PaymentRequirements"
    ADD COLUMN "UpdatedBy" bigint REFERENCES public."Accounts"(id),
    ADD COLUMN "UpdatedAt" timestamptz DEFAULT now();
  -- same for "ProjectRequirements"
  ```
  and in `upsert_requirement`, add `"UpdatedBy": session.get("user_id"), "UpdatedAt": "now()"`
  to the upsert payload. Surface both in the compliance table as a hover title on the select.
  The fuller version — an append-only `RequirementHistory` table capturing every transition —
  is the real audit answer and worth it eventually, but the two columns get you 80% of the value
  today and are a strictly smaller change. Same treatment is worth considering on
  `Invoices.Status` / `Receipts.Status`, which drive the computed slots.

---

### 🟠 High — Table headers and detail labels fail WCAG AA contrast

- **Location:** `static/style.css:302-316` (`.data-table th`), `:426-431` (`.modal-header h2`),
  `:587-594` (`.detail-label`)
- **Issue:** All three use `color: var(--primary)` (`#2B4C9F`) on the dark backgrounds
  `--bg-light` (`#252E42`) / `--bg-mid` (`#1A2332`) / `--bg-dark` (`#0F1624`). Computed contrast
  ratios:
  - `.data-table th` — `#2B4C9F` on `#252E42`: **1.70:1** (needs 4.5:1; 12.8px bold is not
    "large text")
  - `.detail-label` — `#2B4C9F` on `#0F1624`: **2.27:1** (needs 4.5:1)
  - `.modal-header h2` — 28px bold, so the 3:1 large-text threshold applies: still **~1.7:1**
- **Why it matters:** Every column header in the app is effectively unreadable — a saturated
  dark blue on dark navy. This is not a subjective design note; it is below half the required
  ratio, and it affects the labels that tell the user what they are looking at. It will also be
  the first thing any automated audit (Lighthouse, axe) flags on this repo.
  Credit where due: the *body* text is fine — `--text-secondary` `#B8C5E0` on `--bg-mid` is
  **9.1:1**, comfortably AA. The problem is isolated to `--primary` used as a foreground color,
  which it was never light enough to be.
- **Fix:** Introduce a foreground-only variant and use it for text; keep `--primary` for
  backgrounds, borders, and fills where it works well.
  ```css
  --primary-text: #8BA6D9;   /* = --accent; 6.8:1 on --bg-light, 8.4:1 on --bg-dark */
  ```
  Swap `color: var(--primary)` → `var(--primary-text)` at the three locations above. `--accent`
  already exists and already passes, so this is a rename plus three substitutions.
- **Same file, related:** the focus rings at `:247-251` and `:491-497` are
  `rgba(255, 107, 53, 0.1)` — an orange left over from a previous palette, at 10% alpha over a
  dark background. That is a barely-visible focus indicator, which fails §E's "visible focus
  states" for keyboard users. The `box-shadow`s on `.btn-primary` (`:211`, `:219`) and
  `.nav-btn.active` (`:178`) are the same orphaned orange. Repoint all of them at `--primary`
  / `--accent` and raise the focus-ring alpha to something you can actually see (0.35+, or use
  the `outline` approach already used correctly by `.compliance-select:focus` at `:859-862`).

---

### 🟡 Medium — Raw database errors are returned to the client

- **Location:** every `except Exception as e: return jsonify({"error": str(e)})` — 20 occurrences
  across `app.py`
- **Issue:** PostgREST/Supabase exception strings carry table names, column names, constraint
  names, and often fragments of the failing statement. These go straight into a JSON response
  and, via `showNotification('Error: ' + result.error, 'error')` (`app.js:753`), into an
  `alert()` box in front of the user.
- **Why it matters:** Two costs. Security: it hands an attacker a free schema map (§C, "error
  messages don't expose stack traces or internals"). Usability: a compliance officer sees
  `insert or update on table "Invoices" violates foreign key constraint
  "Invoices_ProjectCode_fkey"` and has no idea what to do. It is also *currently* the only
  visible symptom of open gotcha #12 (see below).
- **Fix:** One helper, replacing all 20 sites:
  ```python
  def _fail(e, msg="Could not complete the request", code=400):
      app.logger.exception(msg)          # full detail stays server-side
      return jsonify({"success": False, "error": msg}), code
  ```
  Keep the specific messages you have already written where they help — the FK-violation
  translation at `app.py:605-606` is exactly the right pattern and worth extending to the
  common cases (unique violation → "that code is already in use"; not-null violation → "X is
  required").

---

### 🟡 Medium — No pagination anywhere; the compliance report can silently truncate

- **Location:** all seven `GET` endpoints; `app.py:538-545` (`get_compliance_report`)
- **Issue:** Every list endpoint does `.select("*")` with no `.range()`/`.limit()`, and returns
  the entire table. Supabase's PostgREST applies a server-side row cap (`db-max-rows`, commonly
  1000 by default) and returns the truncated set **without an error**. The client has no way to
  detect it.
- **Why it matters:** For `/api/payments` this is a performance issue. For
  `/api/compliance_report` it is a correctness issue with the worst possible failure direction:
  a payment past the cap does not appear as `Missing` — it does not appear *at all*. An absent
  row reads as "nothing to do here," which is a stronger false-negative than any status value
  could produce. Everything else in this codebase is carefully designed so that gaps surface;
  this one makes them vanish. At current data volumes it is not yet biting, which is exactly why
  it is worth fixing before it does.
- **Fix:** Check your project's `max-rows` setting first. Then either raise it deliberately and
  document the ceiling, or paginate: `.range(offset, offset + limit - 1)` driven by query params,
  with the total from `count='exact'` returned alongside. Minimum viable safety net today — one
  query, one line — is to fetch `count` and compare it against `len(res.data)`, returning an
  explicit `truncated: true` flag the frontend can show as a banner. Loud beats silent.

---

### 🟡 Medium — The compliance views will not scale; the join columns are unindexed

- **Location:** `sql/phase4_requirements.sql:100-126` (`CROSS JOIN LATERAL` with five correlated
  subqueries per project), `:161-181` (four joins + two grouped subqueries per payment); schema
  in `agent.md` (no index declarations)
- **Issue:** `invoice_compliance` runs five correlated subqueries **for every project**, each
  scanning `Invoices` or `Payments`. `compliance_report` then joins that per payment. In
  Postgres, declaring a foreign key does **not** create an index on the referencing column — so
  `Invoices."ProjectCode"`, `Receipts."PaymentCode"`, `Payments."ProjectId"`, and
  `Payments."SupplierId"` are all likely unindexed, and `Invoices."ProjectCode"` is a *text*
  join executed five times per project.
- **Why it matters:** The report is fully recomputed on every tab click. Fine at tens of rows,
  visibly slow at thousands, and it degrades superlinearly (projects × invoices). The
  compute-in-view design is right and worth keeping — it just needs the indexes it assumes.
- **Fix:** Cheap and high-value:
  ```sql
  CREATE INDEX IF NOT EXISTS "Invoices_ProjectCode_idx"  ON public."Invoices" ("ProjectCode");
  CREATE INDEX IF NOT EXISTS "Receipts_PaymentCode_idx"  ON public."Receipts" ("PaymentCode");
  CREATE INDEX IF NOT EXISTS "Payments_ProjectId_idx"    ON public."Payments" ("ProjectId");
  CREATE INDEX IF NOT EXISTS "Payments_SupplierId_idx"   ON public."Payments" ("SupplierId");
  ```
  Then measure before restructuring anything: `EXPLAIN ANALYZE SELECT * FROM compliance_report;`
  with realistic row counts. If it is still slow after indexing, the next step is rewriting the
  five correlated subqueries in `invoice_compliance` as a single grouped aggregate over
  `Invoices` joined once — same result, one scan instead of five. Don't do that until the
  numbers say to.

---

### 🟡 Medium — `localStorage` column order: unguarded parse can brick startup, stale orders resurrect dropped columns

- **Location:** `app.js:452-455` (`loadColumnOrders`), `:461-463` (`getColumnOrder`), `:524-534`
- **Issue:** Two problems in ~10 lines.
  1. `JSON.parse(stored)` has no `try`. `loadColumnOrders()` is the *first* call in the
     `DOMContentLoaded` handler (`:262`), so one corrupt entry throws before `loadLookupData`,
     `loadData`, and `setupEventListeners` ever run — a blank page with no visible error and no
     working UI. Nothing in the app can recover from it; the user must know to clear
     localStorage.
  2. `getColumnOrder` returns the saved array verbatim, never intersected against the current
     `tableConfigs[table].columns`. Anyone who saved a column order before the 2026-07-19
     migration still has `Fatura` and `Makbuz` in their stored order, so those columns keep
     rendering (as `—`, via `formatCell(col, undefined)`) against columns that no longer exist.
     `agent.md` gotcha #6 documents "clear localStorage" as the workaround — which is a known
     bug with a manual workaround rather than a fix.
- **Why it matters:** Neither loses data, but #1 is a total-failure mode triggered by something
  entirely outside the user's control, and #2 means the app's displayed schema can silently
  diverge from the real one — in a tool whose entire value proposition is that its display
  matches reality.
- **Fix:** Both are one line each:
  ```js
  function loadColumnOrders() {
      try { columnOrders = JSON.parse(localStorage.getItem('columnOrders')) || {}; }
      catch { columnOrders = {}; }        // corrupt entry must never block boot
  }
  function getColumnOrder(table) {
      const valid = tableConfigs[table].columns;
      return (columnOrders[table] || valid).filter(c => valid.includes(c));
  }
  ```
  The `filter` alone resolves gotcha #6 permanently — you can delete that entry from `agent.md`.
  It drops removed columns but won't surface *newly added* ones for users with a saved order;
  appending `...valid.filter(c => !saved.includes(c))` handles that too if you want it complete.

---

### 🟡 Medium — Status vocabularies are enforced in one endpoint out of eight

- **Location:** `app.py:552-578` (`/api/requirements`, validated) vs. `:292-345`, `:348-391`,
  `:464-531` (Payments/Invoices/Receipts/Projects `Status`, unvalidated); no `CHECK` constraints
  in the schema
- **Issue:** `upsert_requirement` does this exactly right — explicit `_PAYMENT_DOCS`,
  `_PROJECT_DOCS`, `_SLOT_VALUES` allowlists, reject-by-default, and computed slots
  structurally unwritable. None of that rigor is applied to the six-stage `Status` on Payments,
  Invoices, Receipts, or Projects, which accept any string from any client.
- **Why it matters:** Credit first: I traced every unrecognized-status path through the views and
  they **all fail safe** — an unknown `Invoices.Status` is excluded from `invoiced_in_hand`
  (→ less coverage), an unknown `Receipts.Status` falls to the `ELSE 'Missing'` branch, and an
  unknown status blocks `all_translations_done`. The `CASE` ordering was clearly written with
  this in mind and it holds. So this is not currently a false-`Collected` vector.
  The cost is different: a typo'd status is *accepted, stored, and silently ignored* by the
  compliance engine. `"received"` (lowercase) from an n8n node would leave the officer looking
  at a receipt marked Received in the Receipts tab while the compliance report says `Missing`,
  with nothing explaining the contradiction. And the safety depends on every future view author
  preserving that `CASE` ordering, which is a convention rather than a guarantee.
- **Fix:** `CHECK` constraints, so the vocabulary is enforced where every writer meets it:
  ```sql
  ALTER TABLE public."Invoices" ADD CONSTRAINT "Invoices_Status_check"
    CHECK ("Status" IN ('Missing','Requested','Received','Translated','Sent','Done'));
  -- same for "Receipts"; Payments and Projects have their own vocabularies
  ALTER TABLE public."PaymentRequirements" ADD CONSTRAINT "PaymentRequirements_Status_check"
    CHECK ("Status" IN ('Missing','Unnecessary','Requested','Collected'));
  -- same for "ProjectRequirements"
  ```
  Postgres `CHECK` over a Postgres `ENUM` type deliberately: adding a value to an enum is a
  schema migration, and this vocabulary has already changed once. `CHECK` is a one-line
  `ALTER`.

---

### 🟡 Medium — Multi-step creates are not atomic; a mid-sequence failure leaves an orphan and invites a duplicate

- **Location:** `app.py:248-289` (`create_project`: 3 inserts), `:292-345` (`create_payment`:
  1 insert + 1 select + 2 inserts)
- **Issue:** Four sequential Supabase calls inside one `try`. If any call after the first fails,
  the earlier writes stand, and the handler returns `400 {"success": false}` **without the id of
  the row that was actually created**. The frontend shows "Error", the officer re-submits, and
  now there are two payments.
- **Why it matters:** This is not hypothetical here. `agent.md` gotcha #11 documents that the
  shared global Supabase client throws `EAGAIN` under concurrent use — a live, reproduced,
  *mid-sequence-capable* failure mode, and one that gets substantially more likely in Phase 5
  when n8n hits the API alongside the UI. The compliance direction is safe (a duplicate payment
  inflates `spend_to_document`, making coverage harder), but duplicate payment rows in a
  financial record are their own problem, and an orphaned payment with no receipt row is a
  reconciliation headache.
- **Fix:** The correct fix is a single Postgres function called via `supabase.rpc(...)`, so the
  payment + receipt + requirement seeds commit or roll back together:
  ```sql
  CREATE FUNCTION public.create_payment_with_children(...) RETURNS bigint
  LANGUAGE plpgsql AS $$ ... $$;   -- one transaction, all-or-nothing
  ```
  That is the right amount of machinery for money. If you want the smaller intermediate step
  first: return the created id even on partial failure, with an explicit
  `{"success": false, "partial": true, "id": payment_id}` so the UI can say "the payment was
  saved but its receipt was not — do not re-submit." Ugly, but it stops the duplicate, which is
  the actual harm.

---

### 🟡 Medium — Login throttle grows without bound and enables targeted lockout

- **Location:** `app.py:620-632`, `:664-668`, `:687`
- **Issue:** `_failed_logins` is a module-level dict keyed by username. `_too_many_failures`
  prunes stale timestamps for the queried username but never removes the key itself, and entries
  are only deleted on a *successful* login (`:692`). An attacker posting logins for
  `user0001`…`user999999` creates a permanent dict entry each time — unbounded memory growth
  from unauthenticated requests. Separately, because the lockout is keyed on username only,
  five deliberate failures lock a known colleague out for 15 minutes, repeatable indefinitely.
- **Why it matters:** Both are denial-of-service, neither is a bypass. The comments correctly
  identify this as a stopgap pending Flask-Limiter, and that judgement is sound — I am flagging
  it because the memory growth is not mentioned anywhere and is triggerable by an unauthenticated
  client, which is a different risk class from "the throttle is basic."
- **Fix:** Until Flask-Limiter lands, cap the dict — evict entries whose newest timestamp is
  older than `_LOCKOUT_SECONDS` on each call, or use a bounded structure:
  ```python
  _failed_logins = OrderedDict()   # ponytail: bounded LRU, replace with Flask-Limiter on VPS day
  ```
  with a `while len(_failed_logins) > 10_000: _failed_logins.popitem(last=False)`. For the
  lockout DoS, adding an IP dimension (lock the *pair*, not the username) is the standard answer
  and comes free with Flask-Limiter. Worth one line in the VPS checklist so it isn't rediscovered.

---

### 🟡 Medium — No security headers

- **Location:** `app.py` — no `after_request` hook
- **Issue:** No `Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`,
  `X-Content-Type-Options`, or `Referrer-Policy`. The app is framable (clickjacking: an attacker
  page frames it invisibly and harvests clicks on a logged-in session) and has no CSP to blunt
  the XSS finding above.
- **Why it matters:** Low urgency while loopback-only, but these are the cheapest defence-in-depth
  available and CSP is the second line behind the XSS fix — if escaping is missed anywhere,
  a `script-src 'self'` policy still blocks inline injected handlers.
- **Fix:** One hook, ~8 lines:
  ```python
  @app.after_request
  def _security_headers(resp):
      resp.headers['X-Content-Type-Options'] = 'nosniff'
      resp.headers['X-Frame-Options'] = 'DENY'
      resp.headers['Referrer-Policy'] = 'no-referrer'
      resp.headers['Content-Security-Policy'] = (
          "default-src 'self'; img-src 'self' https:; "
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
          "font-src https://fonts.gstatic.com")
      return resp
  ```
  Note that CSP will *break* the app if the external font/logo hosts aren't allowed — which is
  a good prompt to self-host them (see the Low finding below) and then tighten to
  `default-src 'self'` with no exceptions.

---

### 🟡 Medium — Zero tests, on logic that is entirely about money and correctness

- **Location:** repo-wide (`pytest==8.4.1` is in `requirements.txt`; there is no test file)
- **Issue:** No tests exist. The untested logic includes the amount-coverage rule, the
  four-state derivations, `_to_bool`'s deliberate `True` bias, `DaysToClose`, and the
  `closed` aggregate.
- **Why it matters:** Three of this review's blockers are *logic* bugs in the views — precisely
  what a handful of fixture-based tests would have caught, and precisely what will regress
  silently the next time the formulas are touched (they have already been superseded once). This
  is also, bluntly, the most common thing a reviewer looks for in a portfolio repo and does not
  find.
- **Fix:** Don't build a test suite. Build *one* file that pins the compliance rules — that is
  where the value is concentrated:
  ```python
  # test_compliance.py — the rules that must never silently flip to "done"
  def test_null_status_payment_still_counts_as_spend(): ...
  def test_mixed_currency_does_not_read_collected(): ...
  def test_zero_spend_reads_missing_not_collected(): ...
  def test_to_bool_defaults_true_on_blank(): ...
  ```
  Point them at a scratch Supabase project (or a local Postgres with the same DDL) seeded with
  five rows. Every test above corresponds to a blocker in this review — write them as you fix,
  and each one proves its fix landed. `_to_bool` and `DaysToClose` are pure functions and need
  no database at all; start there for the fastest first green.

---

### 🟡 Medium — Accessibility gaps beyond contrast

- **Location:** `templates/index.html:34-41`, `:58-59`; `app.js:272-280`, `:623-657`
- **Issue:** Four distinct items:
  1. `aria-pressed` is set statically in the HTML (Payments `true`, all others `false`) and the
     nav click handler (`app.js:275-276`) only toggles the `active` **class**. A screen-reader
     user is permanently told "Payments, pressed" no matter which tab is open.
  2. The search input's `<label>` is commented out (`index.html:58`), leaving it announced only
     by its placeholder — which disappears on input.
  3. The modals declare `role="dialog" aria-modal="true"` correctly but have no focus
     management: focus is never moved into the dialog, never trapped, never restored to the
     trigger on close, and `Escape` does not close them. Keyboard users can tab straight out of
     an "open" modal into the page behind it.
  4. `handleFormSubmit` errors surface only via `alert()`; form validation errors have no
     `aria-describedby` association with their fields.
- **Fix:** All small, in rough value order:
  ```js
  // in the nav handler, alongside the class toggle:
  document.querySelectorAll('.nav-btn').forEach(b => b.setAttribute('aria-pressed', b === e.target));
  ```
  Uncomment the label (the `.visually-hidden` class it references needs to exist in `style.css` —
  it currently doesn't). For the modals: on open, `modal.querySelector('input,select,textarea')?.focus()`
  and store `document.activeElement` to restore on close; add a `keydown` listener for `Escape`.
  A full focus trap is more work — `<dialog>` with `.showModal()` gives you trapping, `Escape`,
  and focus restore natively and is well supported now, which is the lazier and better answer if
  you're willing to restructure the two modals.

---

### 🟡 Medium — i18n: a bilingual UI declared as English, with US number formatting on TRY amounts

- **Location:** `templates/index.html:2` (`<html lang="en">`), `app.js:244-248`, `:53`,
  `:436-439`, `:594-599`
- **Issue:** The UI mixes English and Turkish — `Ödeme Emri`, `Teslim Belgesi`,
  `Alındı Belgesi`, `Fotograflar`, `Karar No.`, plus Turkish bank names in a hardcoded array
  (`app.js:53`) — while the document declares `lang="en"`. Amounts are formatted with
  `toLocaleString('en-US')`, producing `1,234.56` for values that are often TRY, where the
  local convention is `1.234,56`. Currency is displayed as a separate column rather than
  formatted with the amount.
- **Why it matters:** The `lang` mismatch makes screen readers pronounce Turkish strings with
  English phonetics (§E). The number formatting is a subtler correctness risk: `1,234` and
  `1.234` differ by a factor of 1000 depending on which convention the reader assumes, and this
  is a financial table read by Turkish and international staff. Every user-facing string is
  hardcoded in JS, so there is no path to localizing later without a rewrite of `tableConfigs`.
- **Fix:** Minimum: wrap Turkish labels in `<span lang="tr">`, and use
  `Intl.NumberFormat(locale, {style:'currency', currency: row.Currency})` — one call that
  handles separators, decimals, and the symbol together, replacing the manual
  `toLocaleString` + separate currency column. It also removes the `parseFloat` on a possibly
  non-numeric value at `:595`. Full i18n (a strings table, locale switching) is not worth it for
  a single-org internal tool — say so explicitly in `project-context.md` so it reads as a
  decision rather than an oversight.

---

### 🟡 Medium — Runtime dependencies on third-party hosts, and hardcoded client branding

- **Location:** `static/style.css:1` (Google Fonts `@import`), `templates/index.html:17` and
  `templates/login.html:13` (logo from `hayirsosyal.org`)
- **Issue:** Fonts and the logo load from external hosts at runtime. Two consequences: the app
  degrades visibly (unstyled fonts, broken logo) with no internet or if either host is down, and
  every page load leaks each user's IP and referrer to Google and to the org's public web host —
  including from the login page, before authentication.
  Separately, this **contradicts a documented decision**: `agent.md` → "Branding & Design" states
  branding is a per-deployment placeholder (`<LOGO_URL>`, `<ORG_NAME>`, `<HEADER_FONT>`) and that
  `agent.md` is "generic/reusable by design — client branding lives there as a placeholder, not
  hardcoded" (`CLAUDE.md`). The actual client's logo URL is hardcoded in two templates.
- **Fix:** Self-host both — download the two font families into `static/fonts/` with a local
  `@font-face`, and save the logo to `static/logo.webp`. That fixes the offline behavior, the
  privacy leak, and the CSP tightening in one move, and removes the two slowest requests on the
  page. Then reconcile the branding decision: either move the values to CSS custom properties /
  a Flask config block so a deployment overrides them in one place, or update `agent.md` to say
  branding is hardcoded per-fork. Either is fine — the current state where the doc and the code
  disagree is not.

---

### 🟡 Medium — Gotcha #12 is still open and now blocks real data entry

- **Location:** `app.py:443-461` (`update_project` writes `ProjectCode`); FK definitions in
  `agent.md` (`Invoices.ProjectCode`, `Receipts.ProjectCode` → `Projects(ProjectCode)`, no
  `ON UPDATE CASCADE`)
- **Issue:** Not a new finding — `agent.md` gotcha #12 documents it precisely and correctly. I am
  re-raising it because it is still unfixed, it is marked "PRIORITY before populating real data,"
  and the review's remit is to flag what blocks the work. `update_project` still writes
  `ProjectCode`, and the edit form still offers the field (`app.js:82`), so the first time anyone
  fixes a typo in a project code that already has invoices, Postgres rejects it and the raw
  FK-violation text lands in an `alert()`.
- **Fix:** Decide now, before data goes in. Both options in the gotcha are reasonable;
  **making the code immutable is the smaller and safer one** — drop `ProjectCode` from
  `update_project`'s write dict and render it as a read-only field in edit mode. `ON UPDATE
  CASCADE` is more convenient but means a text primary identifier can change under rows that
  reference it, which is a class of surprise worth avoiding in an audit trail. Whichever you
  choose, close the gotcha out in `agent.md` — an open item marked "PRIORITY" that sits for two
  days is how the doc-vs-code drift this project has already been bitten by three times starts
  again.

---

### 🟢 Low — Documentation drift found while verifying claims

Per `CLAUDE.md`'s instruction to treat doc claims as hypotheses, I checked each "resume here"
item against the code. Both are already done:

1. **`CLAUDE.md` "Resume here next" (1)** says `.status-collected` and `.status-unnecessary`
   "don't exist yet." They exist — `static/style.css:849-850`, in the uncommitted working tree.
   Along with `.compliance-select` styling at `:854-862`.
2. **`CLAUDE.md` "Resume here next" (2)** flags `Requirment_States` as a misspelling to rename.
   The constant is `Requirement_States` (`app.js:253`) — spelled correctly. Either it was fixed
   without updating the note, or the note was written from memory.

Both are harmless, but they are the fourth and fifth instances of the doc/code drift pattern
`CLAUDE.md` itself warns about — worth updating the file as part of closing out Phase 4.

Also drifted: `agent.md` lists `flask-cors` in the tech stack and install command (removed
2026-07-19); `sql/phase4_requirements.sql:23` says "Payment-grain slots (6)" where there are 3,
and `:33` says "Project-grain slots (2)" where there are 5 (the inline comment on `:37` lists all
five correctly).

---

### 🟢 Low — Small cleanups

- `app.js:310` — `const result = await response.json();` is assigned and never read. Either act
  on it (see the High finding on notifications) or drop the line.
- `app.js:818-820` — `async function editRecord(id) { openModal(id); }` is an async wrapper
  around a sync call, and appears to be unreferenced since the Details-modal refactor. Delete.
- `app.js:810`, `:815` — `setTimeout(..., 300)` hardcodes the modal's CSS animation duration in
  JS. If the CSS changes, these desync. Use the `transitionend` event, or hoist `300` to a named
  constant next to the CSS variable it mirrors.
- `app.js:629` — `'Add New ${tableName}'.replace('${tableName}', ...)` on a single-quoted string
  is a template literal that lost its backticks and got patched with `.replace`. Works; reads as
  a mistake. Use a real template literal.
- `style.css:825-832` — dead status classes (`status-pending`, `-approved`, `-rejected`,
  `-paid`, `-verified`, `-suspended`) match no value in any vocabulary. Already noted in
  `agent.md` gotcha #9; still there.
- `sql/phase4_requirements.sql:29`, `:38` — the `Notes` column on both Requirements tables is
  never written or read by anything. Either wire it into the compliance UI (a per-slot note is
  genuinely useful for "why is this Unnecessary?") or drop it.
- `style.css:312-316` — `position: sticky; top: 0` on `th` inside `.table-wrapper` (which has
  `overflow-x: auto` and no `max-height`) never engages: there is no vertical scroll container,
  so headers scroll away with the page on long tables. Add `max-height` to the wrapper to make
  sticky headers actually work, or drop the sticky.
- `style.css:286-289` — `.table-container { min-width: 100%; overflow: visible }` inside an
  `overflow-x: auto` parent does nothing. Drop the element or the rule.
- `app.py:45-48` — `SUPABASE_URL`/`SUPABASE_KEY` are read with no presence check, so a missing
  var surfaces as an opaque `create_client(None, None)` failure. `FLASK_SECRET_KEY` right above
  it fails loudly with instructions — apply the same treatment for consistency.
- `app.py:145` — the 90-day close window is a bare magic number. `CLOSING_WINDOW_DAYS = 90` at
  module level, since it is a policy value someone will eventually want to change.

---

### 💡 Suggestion — Rename `Receipts.PaymentCode`

Three different things in this schema are called a "Code": `Payments.PaymentCode` (text,
human-facing), `Receipts.PaymentCode` (**bigint FK to `Payments.id`**), and
`Projects.ProjectCode` (text, an actual FK target). That collision has already caused two
documented bugs — gotcha #4 and gotcha #13, the latter of which silently nulled the
Receipt↔Payment link on every edit and broke `receipt_compliance`'s join.

Renaming `Receipts.PaymentCode` → `Receipts.PaymentId` costs one `ALTER TABLE ... RENAME COLUMN`,
one line in `receipt_compliance` (`:67`), and four occurrences in `app.py`/`app.js`. It removes
the entire class of confusion permanently and makes the code self-documenting — `PaymentId` next
to `ProjectId` matches the convention `Payments` already uses. Worth doing before there is more
code referencing it, and it reads well in a portfolio repo where the naming *is* the explanation.

---

### 💡 Suggestion — Surface the coverage numbers in the UI

`invoice_compliance` already computes and exposes `spend_to_document` and `invoiced_in_hand`
(`:81-82`), and `compliance_report` drops them. Adding two read-only columns to
`complianceColumns` turns "Invoice: Requested" into "Invoice: Requested — 4,000 of 5,000
documented." That is the difference between a status a user trusts and a status a user
second-guesses, it makes the currency-mixing blocker visible the moment it happens, and it is
about six lines of config.

---

### 💡 Suggestion — Two `ponytail:` markers worth leaving in the code

Both of these are deliberate, defensible shortcuts that will look like oversights to the next
reader (including future you):

```python
# ponytail: in-process throttle, single-worker only — Flask-Limiter on VPS day  (app.py:620)
# ponytail: global Supabase client, not concurrency-safe — per-request client in Phase 5  (app.py:48)
```

The reasoning already exists in `agent.md`; a one-line marker at the code site is what makes it
findable from the code rather than only from the docs.

---

## What was done well

Genuinely, not as padding:

- **Compute-in-view over a stored cascade.** This is the single best decision in the project.
  "A slot that is never stored cannot drift" is exactly right, and it eliminates the trigger /
  reconciler / staleness class of bug entirely. The reasoning recorded in `CLAUDE.md` is
  better than the reasoning I see in most production codebases.

- **Risk asymmetry is real here, not a slogan.** `DEFAULT 'Missing'`, `ELSE 'Missing'` as the
  terminal branch in every `CASE`, `_to_bool` biasing absent values toward `true`, `IsActive`
  as a kill-switch that fails toward locked-out, default-deny `before_request` instead of
  per-route decorators, and the compliance UI re-fetching after every write so an unsaved value
  can never look real. That is the same principle applied consistently across four layers by
  someone who understood it rather than copied it. My blockers are all cases where the principle
  is *correct* and something underneath it (a nullable column, a missing constraint) routes
  around it — which is a much better problem to have than the principle being absent.

- **Unknown status values fail safe everywhere.** I traced every path a typo'd or unrecognized
  `Status` can take through both views. Every one lands on the pessimistic branch. That is not
  an accident of the code; the `CASE` ordering was clearly written for it.

- **The auth implementation is better than "hand-rolled auth" usually is.** Constant-time
  comparison, a startup-generated dummy hash so unknown usernames take the same time as known
  ones, one generic error message for both failure modes, `session.clear()` before setting keys
  to kill session fixation, `HttpOnly` + `SameSite=Lax`, POST-only logout with the reasoning in
  a comment, and refusing to boot without a real secret key. Each of those is a specific mistake
  that was specifically avoided. `SameSite=Lax` plus a JSON-only, same-origin API also means the
  CSRF exposure is genuinely small — the deferral is correct, not lazy.

- **The comments explain *why*, which is the hard kind.** `app.py:11` (load order),
  `:55-66` (why a DB DEFAULT doesn't fire on an explicit `None`), `:614-617` (the timing-attack
  rationale), `app.js:320-324` (why a fetch wrapper beats eight copies of the same `if`),
  `:646-648` (`??` vs `||` and the falsy-value bug it fixed), `:341-346` (why lookups load
  sequentially). These are the notes of someone reasoning about the code, not narrating it.

- **`/api/requirements` is a well-designed endpoint.** Explicit allowlists, reject-by-default,
  computed slots made structurally unwritable rather than merely undocumented, upsert doubling
  as the backfill path so unseeded rows self-heal on first edit. If the other seven endpoints
  had this shape, three findings above would not exist — it is worth treating this one as the
  house pattern and bringing the rest up to it.

- **`.env` hygiene is correct.** Gitignored, never committed — `git log --all -- .env` is empty,
  and `git ls-files` confirms it was never tracked. `generate_hash.py` uses `getpass` so the
  password never reaches shell history, checks confirmation, enforces a minimum length, and
  explains why the salt differs per call. That is careful work.

- **The documentation discipline is unusual and worth keeping.** Three files with three clearly
  separated jobs, an explicit instruction to distrust all of them, and a running gotchas log
  with resolved entries kept for history. The two stale claims I found are minor precisely
  *because* the system that surfaces them exists.

---

## Suggested order of work

1. `host='127.0.0.1'` — one word, closes the Blocker (`app.py:730`).
2. The `NOT NULL` + `CHECK` migration — closes Blocker #2 and the Amount High, ~10 lines of DDL.
3. Currency-aware coverage — Blocker #3; needs your domain decision first.
4. `UNIQUE` on `Receipts.PaymentCode`, and drop the auto-created placeholder invoice — closes two
   Highs with a constraint and a deletion.
5. The `esc()` helper — before Phase 5 wires up document intake, not after.
6. `_patch()` for the seven PUTs — before n8n writes anything.
7. `requirements.txt` (4 lines) and the README — highest portfolio value per minute spent.
8. Everything else in severity order.

Items 1, 2, 4, and 7 are together under an hour of work and remove two blockers, two highs, and
the repo's worst first impression.
