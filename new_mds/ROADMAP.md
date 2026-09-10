# Detailed Build Roadmap — From Empty Folder to Feature Parity

Use this as a build log as well as a checklist. Do not check an item until you have run its verification step. The goal is parity with the current app described in this folder, not an uncontrolled feature expansion.

## How to use this roadmap

- Work in order: database → Flask → browser for each vertical slice.
- Commit after every checked milestone with a meaningful message.
- Record unexpected behavior in a `notes/` file before asking AI to fix it.
- When an item says **prove**, capture the exact request/response, SQL query, or screenshot in your own notes.
- If you improve an implementation (for example, make a creation flow transactional), retain its visible behavior and update your documentation.

## 0. Define the project and protect the workspace

- [ ] Create a new Git repository and a private remote if you use one.
- [ ] Add `.gitignore` entries for `.env`, `.venv/`, Python caches, editor files, and test artifacts.
- [ ] Copy the documents in `new_mds/` into the new project's `docs/` folder.
- [ ] Read `01-product-brief.md` and write one paragraph in your own words explaining why false completion is worse than false missing.
- [ ] Read `03-data-model.md` and redraw the entity map without looking.
- [ ] Decide your project name, organization branding placeholder, and local port.
- [ ] Create a `DECISIONS.md` file and record: no uploads, no notifications, one currency per project, and no public sign-up in v1.
- [ ] Create a `CHANGELOG.md` and an empty `notes/` folder for verification evidence.
- [ ] Commit the project skeleton and documentation.

**Prove:** `git status` shows no secrets and a clean first commit exists.

## 1. Prepare Python and Supabase safely

- [ ] Install a supported Python 3 version.
- [ ] Create and activate `.venv`.
- [ ] Add `Flask`, `python-dotenv`, `supabase`, and `Werkzeug` to `requirements.txt` with tested versions.
- [ ] Run `pip install -r requirements.txt` in the virtual environment.
- [ ] Create a new Supabase project and note its URL without committing it.
- [ ] Create `.env.example` with keys but no values.
- [ ] Create ignored `.env` containing `SUPABASE_URL`, `SUPABASE_KEY`, and `FLASK_SECRET_KEY`.
- [ ] Generate `FLASK_SECRET_KEY` with `secrets.token_hex(32)`.
- [ ] Create `generate_hash.py` that calls Werkzeug `generate_password_hash` from a supplied password without writing plaintext to a file.
- [ ] Add a short setup section to your root README.
- [ ] Commit dependency and setup files, excluding `.env`.

**Prove:** start a one-line Python process that loads `.env` and confirms the three variable names are non-empty without printing values.

## 2. Plan and create the base database schema

- [ ] Create `sql/001_base_schema.sql`; put the migration name/date/purpose at its top.
- [ ] Create quoted tables: `Suppliers`, `Donors`, `Decisions`, `Projects`, `Payments`, `Invoices`, `Receipts`, and `Accounts`.
- [ ] Add generated numeric primary keys to every table.
- [ ] Make `Donors.DonorCode`, `Decisions.DecisionNumber`, and `Projects.ProjectCode` unique.
- [ ] Add `Projects.SupplierId → Suppliers.id` FK.
- [ ] Add required `Payments.ProjectId → Projects.id` and `Payments.SupplierId → Suppliers.id` FKs.
- [ ] Add optional `Payments.DonorId → Donors.id` and `Payments.DecisionId → Decisions.id` FKs.
- [ ] Add `Invoices.SupplierId → Suppliers.id`, `Invoices.DonorId → Donors.id`, and `Invoices.ProjectCode → Projects.ProjectCode` FKs.
- [ ] Add `Receipts.ProjectCode → Projects.ProjectCode` and `Receipts.PaymentCode → Payments.id` FKs.
- [ ] Confirm `Receipts.PaymentCode` is bigint/numeric, while `Payments.PaymentCode` remains a human display text code.
- [ ] Add all field names listed in `03-data-model.md`, including description/notes/assignee/translation fields.
- [ ] Apply the migration in a development Supabase database.
- [ ] Inspect tables, constraints, and FK types in the Supabase SQL editor.
- [ ] Insert one minimal supplier/project/payment/receipt chain manually to prove each FK works.
- [ ] Attempt a receipt pointing to a nonexistent numeric payment ID and confirm the database rejects it.
- [ ] Commit the base migration and write its apply result in `CHANGELOG.md`.

**Prove:** save the result of a `information_schema`/Supabase schema inspection in your notes; do not rely only on the migration text.

## 3. Add database-level integrity hardening

- [ ] Write `sql/003_integrity_hardening.sql` as a new migration; do not modify an applied migration.
- [ ] Write preflight queries that stop if legacy payment rows have null/invalid status, amount, or currency.
- [ ] Write preflight queries that stop if projects have missing/invalid currency.
- [ ] Write preflight queries that stop for negative invoice/receipt amounts or invalid document statuses.
- [ ] Write a preflight query that identifies duplicate receipt `PaymentCode` values.
- [ ] Write preflight queries that identify payment/invoice currencies that do not match their project.
- [ ] Backfill missing invoice/receipt status to `Missing` and missing translation flag to `true` only after reviewing the risk.
- [ ] Add NOT NULL/default/check constraints for inputs that power compliance formulas.
- [ ] Add `UNIQUE ("PaymentCode")` to Receipts to enforce at most one receipt per payment.
- [ ] Add non-negative constraints for budget and document amounts.
- [ ] Add check constraints for all four state sets from `03-data-model.md`.
- [ ] Write trigger function: payments must match the selected project's currency.
- [ ] Write trigger function: invoices assigned to a project must match that project's currency.
- [ ] Write trigger function: changing a project currency is rejected when related payments/invoices differ.
- [ ] Explicitly exclude receipts from the project-currency triggers; receipt amount/currency can differ because of bank cuts.
- [ ] Add indexes used by report joins (`Payments.ProjectId`, `Invoices.ProjectCode`, `Receipts.PaymentCode`, `Payments.SupplierId`).
- [ ] Apply the migration in development and record the result.
- [ ] Test every constraint with an intentionally invalid insert/update.
- [ ] Commit the migration.

**Prove:** a direct SQL insert with a mismatched payment currency fails even without Flask running.

## 4. Build the compliance tables and views first

- [ ] Create `sql/002_requirements_and_views.sql` and document that it follows the base schema.
- [ ] Create `PaymentRequirements` with `PaymentId`, `DocType`, `Status`, optional notes, `ON DELETE CASCADE`, and unique `(PaymentId, DocType)`.
- [ ] Create `ProjectRequirements` with analogous fields and unique `(ProjectId, DocType)`.
- [ ] Restrict payment document types to `Dekont`, `TransferOrder`, and `OdemeEmri`.
- [ ] Restrict project document types to `Contract`, `Karar`, `TeslimBelgesi`, `AlindiBelgesi`, and `Fotograflar`.
- [ ] Make requirement status default to `Missing`, never a completed state.
- [ ] Create `receipt_compliance` view using a left join from payments to receipts.
- [ ] Implement receipt calculation: Received-or-later is `Collected`; Requested is `Requested`; otherwise `Missing`.
- [ ] Implement receipt translation calculation: `Unnecessary` when translation is false; `Collected` only at `Done`; `Requested` at Translated/Sent; else `Missing`.
- [ ] Create `invoice_compliance` at project grain.
- [ ] Sum only non-returned payment amounts as spending to document.
- [ ] Sum invoice amounts only when status is Received-or-later as invoice evidence.
- [ ] Make unknown payment amount/status force invoice compliance to `Missing`.
- [ ] Make full coverage return `Collected`; partial active effort return `Requested`; no evidence return `Missing`.
- [ ] Implement invoice translation with conservative/all-required-invoices logic.
- [ ] Create `compliance_report`, one wide row per payment, including identifiers required by the browser to edit a slot.
- [ ] Pivot the eight human requirement slots with absent rows defaulting to `Missing`.
- [ ] Join the four calculated slots; do not store or upsert them.
- [ ] Calculate `closed` as Yes only if all twelve slots are Collected/Unnecessary.
- [ ] Apply the migration and then reapply/refresh views after integrity changes.
- [ ] Write minimal fixture data and manually query all three views.
- [ ] Test that adding a new non-returned payment reopens a previously fully covered invoice slot.
- [ ] Test no translation-required invoice gives `Unnecessary`, not `Collected`.
- [ ] Commit migrations and save query results in notes.

**Prove:** demonstrate at least one case each for `Missing`, `Requested`, `Collected`, and `Unnecessary` using SQL queries.

## 5. Create the Flask app shell and health checks

- [ ] Create `app.py`, load `.env` before reading configuration, and fail loudly if any required environment variable is missing.
- [ ] Initialize Flask and set its secret key from `FLASK_SECRET_KEY` only.
- [ ] Set session cookie `HttpOnly`, `SameSite=Lax`, and an eight-hour permanent lifetime.
- [ ] Add a development-only `/` placeholder route that renders a minimal template.
- [ ] Create `templates/index.html` and `static/style.css`/`static/app.js`; confirm Flask serves them.
- [ ] Create `_get_supabase_client()` that creates a client on `flask.g` once per request.
- [ ] Use a `LocalProxy` or helper so all route code accesses the request-scoped client.
- [ ] Add a temporary protected diagnostic route only while learning, then remove it before committing the feature slice.
- [ ] Run the server at loopback and verify a browser receives the template and static files.
- [ ] Open two browser requests concurrently and confirm there is no shared-client error.
- [ ] Commit the minimal running app.

**Prove:** unset each required environment variable one at a time and confirm startup refuses with a clear non-secret message.

## 6. Implement authentication before business routes

- [ ] Add `Accounts` migration fields and manually seed one active account with a generated Werkzeug hash.
- [ ] Implement `/login` GET with a small server-rendered form.
- [ ] Implement `/login` POST using `check_password_hash`.
- [ ] Create one dummy hash at startup and check it for unknown usernames to reduce timing information.
- [ ] Return the same generic error for unknown username, wrong password, and disabled account.
- [ ] Add in-memory login failure tracking: five failures within fifteen minutes per username for local parity.
- [ ] On success, clear the old session, set only user ID/display name, mark it permanent, and redirect to `/`.
- [ ] Add `/logout` as POST-only; clear session and redirect to login.
- [ ] Add a `before_request` default-deny guard; allow only endpoint names `login` and `static`.
- [ ] Make unauthenticated API requests return JSON `401`; redirect non-API page requests.
- [ ] Add frontend `apiFetch()` that redirects to `/login` on any `401` and stops caller processing.
- [ ] Test login, logout, invalid password, disabled account, expired session, direct protected URL, and direct protected API request.
- [ ] Commit authentication.

**Prove:** add a deliberately new Flask route and confirm it is protected without adding a decorator.

## 7. Build lookup entities end to end

- [ ] Define backend allowed field sets for Supplier, Donor, and Decision.
- [ ] Add GET routes sorted by friendly name/date.
- [ ] Add POST routes with required-field checks and safe error responses.
- [ ] Add PUT routes that implement true partial updates: omitted keeps value, explicit null clears an optional value.
- [ ] Add generic delete support only for the seven allowed entity names; reject all other table names.
- [ ] Create a minimal SPA HTML shell with navigation, add button, search, table, loading region, notification region, and modal.
- [ ] Define JavaScript table configs containing columns, labels, and form fields for Suppliers, Donors, Decisions.
- [ ] Implement a generic table renderer, generic form renderer, and create/edit submit handler.
- [ ] Implement details view and delete confirmation.
- [ ] Fetch/render each lookup entity and verify sorting and form validation.
- [ ] Verify a required database relationship prevents deleting a referenced lookup and shows a useful message.
- [ ] Commit this vertical slice.

**Prove:** create, update only one field, reload, and confirm the unsubmitted fields were preserved.

## 8. Add projects end to end

- [ ] Add Projects GET route with supplier join; flatten a display-only `SupplierName`.
- [ ] Add Flask validators for required values, currency, status, and non-negative budget.
- [ ] Add Projects POST and partial PUT routes using explicit fields.
- [ ] On project creation, insert a draft invoice with matching project code/supplier/currency, Missing status, and translation required.
- [ ] On project creation, seed exactly five project requirements as Missing.
- [ ] Decide and document the temporary atomicity/recovery plan if draft creation fails after project insert.
- [ ] Add Project configuration/form fields in JavaScript, including supplier lookup and Drive folder link.
- [ ] Render project status and Drive folder link appropriately.
- [ ] After successful project creation, show a toast with an action that opens the created invoice in edit mode.
- [ ] Test a valid project and verify database side effects directly.
- [ ] Test invalid budget/currency/status and verify no partial project is created for validation failures.
- [ ] Test project delete behavior when child records exist and record expected result.
- [ ] Commit the project slice.

**Prove:** query invoices and project requirements after creation; there must be exactly one draft invoice and five requirements for the new project.

## 9. Add payments and 90-day countdown end to end

- [ ] Add Payments GET route with supplier/project/donor/decision joins and human-friendly flattened fields.
- [ ] Calculate `DaysToClose` during GET: `90 - (today - PaymentDate).days`; return null if closing date/payment date is absent as appropriate.
- [ ] Add required validations for supplier, project, decision, destination, amount, currency, and payment status.
- [ ] Add Flask-side project-currency validation, then rely on the database trigger as final authority.
- [ ] On payment creation, insert the payment first and capture its numeric ID.
- [ ] Resolve the project code from `ProjectId`.
- [ ] Auto-create one receipt using the numeric payment ID in `Receipts.PaymentCode`, copied payment date/amount/currency, Missing, translation required.
- [ ] Seed exactly three payment requirements as Missing.
- [ ] Add Payment form/table configuration with all lookups and date/status fields.
- [ ] Add deadline color styling: safe at 30+ days, warning below 30, danger below 10.
- [ ] Test payment creation and verify auto receipt + three requirements in SQL.
- [ ] Test payment update to a mismatched currency; expect Flask/database rejection.
- [ ] Test a returned payment is excluded from invoice spending-to-document.
- [ ] Commit the payment slice.

**Prove:** create payment code `PAY-ABC` and verify its generated receipt stores the numeric payment ID, not `PAY-ABC`, in the FK column.

## 10. Add invoices and receipts end to end

- [ ] Add GET invoices with joined supplier/donor display names.
- [ ] Add GET receipts that returns raw numeric `PaymentCode` plus separate `paymentCodeDisplay` text.
- [ ] Add create/update routes with explicit invoice/receipt field allowlists.
- [ ] Validate non-negative amounts, allowed optional currency, and six-stage document statuses.
- [ ] Convert `RequiresTranslation` robustly; absent/blank becomes true.
- [ ] Add invoice project-currency validation on create and when either project or currency changes on update.
- [ ] Add pre-insert API guard against a second receipt for a payment; retain database unique constraint as final authority.
- [ ] Ensure receipt updates do not overwrite its amount/currency from the payment.
- [ ] Add UI configurations for Invoice and Receipt, including translation flag and assignee.
- [ ] Configure project lookup by `ProjectCode` for invoices/receipts and payment lookup by numeric ID for receipts.
- [ ] Verify an edit form populates `false` translation flag correctly; use `??`, not `||`.
- [ ] Verify receipt table displays `paymentCodeDisplay` but form selects raw `PaymentCode` numeric ID.
- [ ] Test a second receipt request fails.
- [ ] Test invoice and receipt status changes update report formulas after reload.
- [ ] Commit invoice/receipt slice.

**Prove:** edit a generated receipt without changing the payment selection; after saving, its report receipt slot remains connected to that payment.

## 11. Build the compliance API and screen

- [ ] Add GET `/api/compliance_report` that selects the view and sorts newest transfer first.
- [ ] Define server allowlists for payment/project document types and four requirement statuses.
- [ ] Add PUT `/api/requirements` that accepts scope, doc type, status, owner ID.
- [ ] Map only valid payment scope/types to `PaymentRequirements` and project scope/types to `ProjectRequirements`.
- [ ] Upsert requirement with conflict key `(owner FK, DocType)`.
- [ ] Reject invalid scope/type/status and all computed slots with `400`.
- [ ] Add a `compliance` navigation tab.
- [ ] Create fixed compliance column config with metadata, eight human columns, four computed columns, and Closed.
- [ ] Make human columns select controls with `data-scope`, `data-doc`, and numeric owner ID data attributes.
- [ ] Render calculated columns and Closed as read-only badges/text.
- [ ] Add one delegated change listener on the table body.
- [ ] Send the PUT payload and always reload the report after it resolves, whether it succeeds or fails.
- [ ] Make compliance layout scroll horizontally on narrow screens.
- [ ] Test each human dropdown persists across page refresh.
- [ ] Attempt to manipulate the browser request to write an Invoice/Receipt calculated slot and confirm API rejection.
- [ ] Test report `Closed` changes to Yes only after all conditions are satisfied, then changes back to No if any one is reset.
- [ ] Commit compliance feature.

**Prove:** take a before/after query of `compliance_report` that shows a calculated status changing purely from Invoice/Receipt data, not from a requirement write.

## 12. Finish generic UI behavior and safe rendering

- [ ] Implement active navigation state and `aria-pressed` updates.
- [ ] Implement global loading display for every fetch path, including compliance.
- [ ] Implement accessible success/error notifications with `aria-live`.
- [ ] Implement modal close/cancel/backdrop behavior and keyboard-focus test it.
- [ ] Implement client-side table search for normal tabs; hide/disable it intentionally for Compliance if it is not supported.
- [ ] Implement per-table draggable column order stored in `localStorage` as `columnOrders`.
- [ ] Implement reset column order and test stale/unknown saved columns do not break rendering.
- [ ] Make Details modal list configured display columns only, never every raw response key.
- [ ] Escape all database-provided text or create DOM nodes with `textContent`; eliminate raw user text in `innerHTML`.
- [ ] Validate URLs before rendering Drive links with `href`.
- [ ] Test supplied strings that contain `<script>`, quotes, ampersands, and URL schemes such as `javascript:`.
- [ ] Check desktop and narrow mobile layouts.
- [ ] Commit UI hardening.

**Prove:** insert an XSS-looking supplier name and confirm it is displayed as literal text, not executable markup.

## 13. Execute the full parity test

- [ ] Create fresh fixture records for supplier, donor, decision, project, and two payments.
- [ ] Confirm project creation makes one invoice and five project requirements.
- [ ] Confirm each payment creation makes one receipt and three payment requirements.
- [ ] Complete documents in a deliberate order: request → received → translated → sent → done.
- [ ] Set a receipt `RequiresTranslation=false` and confirm the translation slot becomes Unnecessary.
- [ ] Set invoice amounts that are below payment total and confirm Invoice is Requested/Missing, not Collected.
- [ ] Raise received-or-later invoice amount to cover all non-returned payments and confirm Invoice becomes Collected.
- [ ] Make translation-required invoices Done and confirm Invoice Translation becomes Collected.
- [ ] Mark each human slot Collected or Unnecessary and confirm Closed becomes Yes.
- [ ] Add a new non-returned payment and confirm Invoice/Closed reopen as required.
- [ ] Set one human slot Missing and confirm Closed becomes No.
- [ ] Confirm lookup values, deadlines, details modal, search, column ordering, logout, and 401 redirect.
- [ ] Run direct SQL invariant tests again after browser testing.
- [ ] Record passed/failed/untested cases in `CHANGELOG.md` or a test report.
- [ ] Tag/commit the feature-parity milestone.

**Prove:** another person can follow your README, run migrations, seed an account, and complete this script without needing access to the original application.

## 14. Release only when authorized

- [ ] Review every item in `06-security-and-release.md` before exposing the app to any network.
- [ ] Set up production environment variables using the hosting platform's secret store.
- [ ] Configure Gunicorn plus HTTPS reverse proxy, then enable secure session cookies.
- [ ] Enable/verify Supabase RLS based on your chosen server access model.
- [ ] Install durable rate limiting and generic error responses.
- [ ] Back up the database and rehearse how to restore it.
- [ ] Run migration preflight checks in production before applying them.
- [ ] Smoke-test login, writes, compliance report, logout, and backup after deployment.
- [ ] Write the deployment URL, deploy time, migration versions, and rollback contact in operations notes.

**Prove:** only complete this section after an authorized production deployment; local feature parity does not count as a security review.

## Optional next steps (not needed for current parity)

- [ ] Make project/payment creation side effects transactional with a PostgreSQL function or server transaction.
- [ ] Decide immutable codes versus `ON UPDATE CASCADE` and implement/migrate safely.
- [ ] Add file staging/upload and human verification workflow.
- [ ] Add n8n read access to the report and project-created webhook only after auth/RLS design.
- [ ] Add exports, dashboard, filtering, user roles, audit log, tests, and monitoring as separate, documented projects.
