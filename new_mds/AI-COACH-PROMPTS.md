# AI Coach Prompts

Use AI as a reviewer and teacher first. Give it the relevant file, expected behavior, and a small goal. Ask for explanation before asking for code, then type or adapt the implementation yourself.

## Start-of-session prompt

> I am rebuilding an NGO compliance tracker in Flask, Supabase PostgreSQL, and vanilla JavaScript. I am currently on roadmap item [paste item]. Teach me the smallest next concept, ask me one checking question, then give me an implementation plan. Do not write the whole feature unless I explicitly ask.

## Schema review

> Review this SQL migration against `03-data-model.md`. Check foreign-key types, nullability, enum constraints, unique rules, and whether any rule can fail open. Return: (1) blockers, (2) risks, (3) exact manual SQL checks I should run. Do not rewrite unrelated code.

## Backend review

> Review this Flask route for input allowlisting, omitted-versus-null update behavior, validation, authentication, error handling, and database invariants. Explain each concern in beginner-friendly language and show only the smallest corrected snippet.

## Frontend review

> Review this vanilla-JS rendering code for XSS, accidental loss of false/zero values, incorrect lookup IDs, accessibility, and stale UI state. Give a test case for every issue you find.

## Compliance logic review

> Treat `Collected` as dangerous if wrong. Given this SQL view and these example rows, compute each compliance slot by hand, identify any false-completion path, and propose test cases. Keep calculated slots read-only.

## Debugging prompt

> I expected [behavior], but observed [actual behavior]. Here are the request payload, response, server log, and relevant code. Help me form three falsifiable hypotheses, tell me the cheapest check for each, and wait for my results before proposing a fix.

## End-of-milestone prompt

> Compare my implementation to the completed roadmap items below. Produce a parity checklist: passed, failed, untested. Then suggest the smallest next milestone. Do not recommend new features outside the documented scope.

## Useful habits

- Ask the AI to explain every query/line you do not understand.
- Ask it for edge cases before writing a feature.
- Have it review diffs, not only final files.
- Run the checks yourself and report actual output back to it.
- Never paste `.env` values, database keys, user data, or production logs containing secrets.
