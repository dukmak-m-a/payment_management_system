# Security, Testing, and Release

## Local setup checklist

- Install Python 3 and create `.venv`.
- Install the four runtime dependencies.
- Create a Supabase project and store only server-side settings in `.env`.
- Create an `Accounts` table and seed one account using a Werkzeug-generated password hash, never a plaintext password.
- Apply base schema, then requirements/views SQL, then integrity-hardening SQL.
- Start Flask loopback-only and visit `http://127.0.0.1:5000`.

## Manual test script

1. Login with valid credentials; verify invalid username and password show the same error.
2. Verify an unauthenticated `/api/payments` request receives `401` and the browser returns to login.
3. Create a supplier, donor, decision, project, and payment in that order.
4. Confirm the project made exactly one draft invoice and five project requirements.
5. Confirm the payment made exactly one draft receipt and three payment requirements.
6. Change the generated receipt to Received/Done and verify receipt columns change only as defined.
7. Add invoice data and verify invoice coverage responds to amount and status changes.
8. Change human requirement statuses and confirm the report refreshes from stored values.
9. Attempt invalid currency, negative amount, second receipt for the payment, and cross-project currency; expect rejection.
10. Set all twelve report slots to satisfied conditions and confirm `Closed = Yes`; unset one and confirm it immediately returns to `No`.
11. Edit a receipt and ensure its numeric payment FK remains connected.
12. Log out and confirm protected pages/APIs are no longer available.

## Automated tests to add as skills grow

- Unit-test validators: amount, currency, status, boolean coercion, deadline calculation.
- Route tests with a mocked Supabase layer: auth default-deny, invalid requirement scope, patch omission behavior, and computed-slot write rejection.
- SQL integration tests: one receipt uniqueness, currency trigger, and each compliance-view truth table.
- Browser smoke tests: create chain, edit lookup fields, compliance dropdown refresh, session-expiry redirect.

## Before public deployment

- [ ] Set `debug=False`; never expose Flask's development server.
- [ ] Run Gunicorn behind Nginx or Caddy with HTTPS.
- [ ] Enable `SESSION_COOKIE_SECURE=True` after HTTPS works.
- [ ] Replace in-memory login throttle with durable rate limiting.
- [ ] Return generic client errors; log detailed errors server-side.
- [ ] Fix all raw `innerHTML` data interpolation/XSS paths.
- [ ] Enable and test Supabase RLS appropriate to the chosen server key.
- [ ] Confirm backups, recovery ownership, dependency updates, and secret rotation process.
- [ ] Run a real multi-request/load test; request-scoped clients solve one class of concurrency problem, not all capacity issues.

## Operations notes

Keep a migration log with date, environment, SQL filename/checksum, result, and rollback/recovery instructions. Do not edit a previously applied SQL migration; add the next numbered migration. Back up database data before destructive schema changes.
