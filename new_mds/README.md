# Build-From-Scratch Guide: NGO Compliance Tracker

This folder is a clean, learning-first blueprint for rebuilding the current application yourself. It documents the intended product rather than asking you to reverse-engineer the existing source as you go.

## Read in this order

1. [01-product-brief.md](01-product-brief.md) — the problem, users, and success criteria.
2. [02-architecture.md](02-architecture.md) — the chosen stack and boundaries.
3. [03-data-model.md](03-data-model.md) — entities, relationships, data rules, and SQL plan.
4. [04-api-and-business-rules.md](04-api-and-business-rules.md) — backend contracts and safety rules.
5. [05-ui-spec.md](05-ui-spec.md) — screens and interaction behavior.
6. [06-security-and-release.md](06-security-and-release.md) — local setup, security, testing, and deployment.
7. [ROADMAP.md](ROADMAP.md) — follow this checkbox-by-checkbox while you build.
8. [AI-COACH-PROMPTS.md](AI-COACH-PROMPTS.md) — prompts that help AI teach and review without doing the thinking for you.

## Target app in one sentence

An authenticated internal web app for an NGO compliance officer to manage suppliers, donors, decisions, projects, payments, invoices, receipts, and document-completeness status for donor-funded payments.

## What "done" means

Feature parity means the rebuilt app has:

- Flask backend, Supabase/PostgreSQL database, vanilla HTML/CSS/JavaScript frontend.
- Login and logout with server-side Flask sessions.
- CRUD interfaces for Suppliers, Donors, Decisions, Projects, Payments, Invoices, and Receipts.
- Automatic creation of one draft invoice per project and one draft receipt per payment.
- A 90-day payment closing countdown.
- A Compliance report where human requirements are editable and invoice/receipt requirements are calculated live.
- Data validation and database safeguards that prevent an item from looking compliant when the data is incomplete.

## Working agreement with yourself

Build vertical slices. For each slice: make the database change, make the backend route, make the UI, then manually prove it works. Commit after each verified milestone. Do not add automation that marks a document complete without a human-confirmable source of truth.

## Deliberate scope boundary

This target does not include file storage/upload, email sending, n8n/Google Drive integration, roles, exports, dashboards, or a public registration flow. Keep a `future-ideas.md` outside the implementation plan so scope does not expand while you learn the core.
