# UI Specification

## App shell

Build one responsive page with a branded header, sign-out button, navigation, action bar, data grid, global loading overlay, notification region, record modal, and column-settings modal.

Navigation tabs:

`Payments` · `Projects` · `Invoices` · `Receipts` · `Suppliers` · `Donors` · `Decisions` · `Compliance`

The first seven tabs share a generic table-and-modal CRUD system. Compliance intentionally has its own renderer because its columns are mixed read-only/editable calculated data.

## Generic CRUD table behavior

- Fetch lookups (suppliers, donors, projects, decisions, payments) at startup and after every successful write.
- Fetch the active table, render its configured ordered columns, and show add, edit, details, and delete actions.
- Use modal form definitions to render text, number, date, textarea, select, and lookup controls.
- Use lookup ID values in form submissions; display friendly names/codes in the table.
- Search only the visible configured columns, client-side.
- Let a user drag/reorder columns and persist each table's order in `localStorage` under `columnOrders`; provide reset.
- Show a loading overlay during requests and a toast for success/failure.
- Make `DriveFolderLink` a safe clickable folder link; ensure HTML rendering is escaped/sanitized before interpolating any database value.

## Entity forms

| Tab | Important form controls |
|---|---|
| Suppliers | company name, country, contact person |
| Donors | donor code, donor name, country, contact person |
| Decisions | number, date, description, attendants, notes |
| Projects | project code, subject, description, supplier lookup, budget, currency, dates, status, Drive link |
| Payments | code, supplier/project/donor/decision lookups, destination, bank, amount/currency/status, payment/declaration/closing dates |
| Invoices | code/no, supplier/donor/project lookups, date, amount/currency, status, requires translation, assignee, notes |
| Receipts | code/no, project/payment lookups, payment/receipt dates, amount/currency, status, requires translation, assignee, notes |

## Project/payment creation experience

- After project creation, show a toast explaining that a draft invoice exists and provide an **Open Invoice** action that switches to Invoices and opens that record.
- Payment creation happens without a second modal; the auto-created receipt appears under Receipts. Its initial status is `Missing`.
- Preserve `false` and `0` when populating an edit form; use nullish handling (`??`) rather than `value || ''`.

## Compliance screen

The report has a fixed column order: payment metadata, the twelve document slots, then `Closed`.

- Render human slots as selects with `Missing`, `Unnecessary`, `Requested`, `Collected`.
- Render calculated Invoice/Fatura/Receipt/Makbuz and `Closed` as read-only text/badges.
- Attach one delegated `change` listener to the table body. Read `scope`, document type, and owner ID from `data-*`; cast owner ID to a number; send `PUT /api/requirements`; always re-fetch the report afterwards, even after a failed request.
- This re-fetch is intentional: the UI must not leave an unsaved selected value visible as if it were the truth.

## Usability/accessibility baseline

- Use semantic buttons, visible labels, keyboard-focus styles, and `aria-live` for notifications.
- Give modals `role="dialog"`, `aria-modal="true"`, and labelled headings; close on Cancel, close button, and backdrop click.
- Use non-color-only status labels. Color deadline cells: green at 30+ days, warning below 30, danger below 10.
- Test narrow screens with horizontal table scrolling rather than hiding compliance data.

## Security warning for the implementation

Do not render database strings directly through `innerHTML`. Build cells with `textContent`, or use a small escaping function everywhere values are interpolated. With cookie-authenticated APIs, an XSS payload can perform actions as the logged-in officer even though the cookie is HttpOnly.
