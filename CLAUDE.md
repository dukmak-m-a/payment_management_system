<!-- Destination: repo root, replaces the current CLAUDE.md -->

# CLAUDE.md — NGO Compliance Tracking App

Loads alongside `~/.claude/CLAUDE.md` (the mentoring contract that applies to every one of my
projects — how to coach, when to write code, review standards). This file holds only what's
specific to *this* app: identity that's stable and small enough to justify being loaded every
session. Nothing dated or volatile belongs here — see the map below for where that goes.

## Four places, four jobs — don't duplicate one inside another

- **`CLAUDE.md`** (this file) — what this app is, the principles that govern every future
  decision, a short pointer to current state. Loads every session — kept small on purpose.
- **`project-context.md`** — the *why*: business context, decisions and their reasoning, the
  Doc-Drift Log, open issues, build/migration history. Read before touching schema or status
  logic.
- **`agent.md`** — the *what*: exact DB schema, API endpoints, gotchas. Generic/reusable by
  design — client branding lives there as a placeholder, not hardcoded.
- **`.claude/rules/schema-audit.md`** — loads automatically, but *only* when you actually touch
  `app.py`, `static/app.js`, or `sql/**` — the three-way field-audit checklist lives there so it
  doesn't cost tokens on sessions that never touch those files.

## Trust nothing in these docs at face value

This project has a confirmed history of docs claiming a fix was "applied" or a decision "made"
while the running code said otherwise — see `project-context.md` → Doc-Drift Log for the exact
instances. Treat any "done" / "fixed" / "decided" claim in any project doc, including this one,
as a hypothesis until checked against the actual running code or DB schema. If you find a
contradiction, say so explicitly — don't silently trust the doc, and don't silently trust the
code either.

## What this app is

Payment/compliance-document tracking for a Türkiye-based NGO/donor-funded program — full
domain context in `project-context.md` §1. This is my portfolio flagship, so code quality and
review rigor should assume a client or hiring manager may eventually read this repo. I have
real domain authority on the compliance workflow itself: if something in the schema doesn't
match how compliance tracking actually works in practice, my instinct is probably right and
worth surfacing as a question, not overriding.

**Application code for this repo** = `app.py`, `static/app.js`, `static/style.css`,
`templates/*.html`, `sql/*.sql`. The global "never write app code unless asked" rule applies to
exactly these paths; `.claude/settings.json` additionally turns edits to them into a
confirmation prompt as a backstop (see setup notes from this handoff for the snippet).

## Core architectural principles (govern every future decision, not just past ones)

Condensed on purpose — full reasoning for each is in `project-context.md` §3.

- **Risk asymmetry is the north star.** False "Missing" self-corrects (a human follows up).
  False "Collected"/"Done" is dangerous — it silently hides a real compliance gap. Every
  computed status must bias toward under-claiming completion.
- **Two-key identity model.** Supplier/company code → contact lookup. Project code
  (= Decision Number) → which document row a payment/upload belongs to. Never re-derive these
  from filenames or free text — they cascade automatically from Project/Payment creation.
- **Staging over confirmation-bots.** Ambiguous documents get a `to_verify` state and live in
  a separate Drive folder until a human confirms — no bot needed for v1.
- **International payments only, for now.** Domestic tracking is deferred by design, not an
  oversight — don't "helpfully" extend logic to domestic payments without being asked.

## Current focus

As of 2026-07-29: Phase 4 (Requirements table + status cascade) is done and verified
end-to-end. Two small deferred items and the full Phase 5/6 roadmap are in
`project-context.md` → Build Log. **Resume there, not here** — this section is intentionally
not a changelog, so it won't need editing every session.
