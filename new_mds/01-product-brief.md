# Product Brief

## Problem

An NGO administering donor-funded projects must collect supporting documents after every payment. The officer needs one trustworthy place to see which documents are missing, requested, received, translated, or complete before the regulatory closing deadline (usually 90 days after payment).

Spreadsheets can list requirements but cannot safely express relationships such as: one project has multiple payments; one invoice may cover several payments; a receipt belongs to exactly one payment; and a payment's documents should affect a report instantly.

## Primary user and jobs

The primary user is an internal compliance officer. They must be able to:

- Register reference records: supplier, donor, and governing decision.
- Create a project for a supplier, with budget, currency, and dates.
- Register a payment and immediately see its deadline and receipt placeholder.
- Track invoice and receipt document progress and translation needs.
- Record the status of manually verified documents.
- Open a report that never reports a payment as closed unless all required slots are truly satisfied.

## Product principles

1. **Completion must fail closed.** A false `Missing` causes review; a false `Collected` can hide a legal problem. Unknown and absent data must therefore read as missing.
2. **Use the right grain.** Receipt-related work is per payment. Invoice coverage and several supporting documents are per project.
3. **Calculate derived status live.** Do not store copies of invoice/receipt compliance status that can become stale.
4. **Keep humans in the loop.** Human-verified documents can be changed by an officer; computed documents cannot be manually overridden.
5. **Prevent mis-keying.** Use database foreign keys and lookup controls; use numeric IDs for IDs and display codes only for humans.

## Core flow

```text
Supplier + Donor + Decision
              │
              ▼
           Project ── creates one draft Invoice
              │
              ▼
           Payment ── creates one draft Receipt and 3 payment requirements
              │
              ▼
    Compliance report combines project and payment requirements
```

## Acceptance criteria

The product is ready for a small internal pilot when a user can create a full chain (supplier → project → payment), edit the generated invoice/receipt, mark human requirements, and see the compliance report update correctly after every change.

## Non-goals for this build

- No document-file upload or Drive synchronization yet.
- No automatic email/WhatsApp/Telegram messages.
- No self-sign-up or public-facing account pages.
- No multi-currency accounting inside a single project. Each project uses one of `TRY`, `USD`, or `EUR`; receipt currency may differ due to bank deductions.
