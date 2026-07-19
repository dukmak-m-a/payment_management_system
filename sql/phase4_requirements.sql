-- =====================================================================
-- Phase 4 — Requirements tables + compliance views
-- NGO Compliance Tracking App
--
-- Run in the Supabase SQL editor. DB-first (per the DB -> backend ->
-- frontend order). Tables use IF NOT EXISTS; views use CREATE OR REPLACE.
--
-- To re-run after CHANGING a view's columns, drop first (reverse dep order):
--   DROP VIEW IF EXISTS public.compliance_report;
--   DROP VIEW IF EXISTS public.invoice_compliance;
--   DROP VIEW IF EXISTS public.receipt_compliance;
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Human-edited requirement slots  (long shape = source of truth)
--    Four-state each: 'Missing' | 'Unnecessary' | 'Requested' | 'Collected'
--    DEFAULT 'Missing' is risk-asymmetry: a slot never defaults toward done.
--    The 4 computed slots (Invoice/Fatura/Receipt/Makbuz) are NOT stored here
--    -- they are derived live by the views below.
-- ---------------------------------------------------------------------

-- 1a. Payment-grain slots (6): one row per Payment x DocType
CREATE TABLE IF NOT EXISTS public."PaymentRequirements" (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "PaymentId"  bigint NOT NULL REFERENCES public."Payments"(id) ON DELETE CASCADE,
  "DocType"    text   NOT NULL,   -- Dekont | TransferOrder | OdemeEmri
  "Status"     text   NOT NULL DEFAULT 'Missing',
  "Notes"      text,
  UNIQUE ("PaymentId", "DocType")
);

-- 1b. Project-grain slots (2): one row per Project x DocType (Contract, Karar)
CREATE TABLE IF NOT EXISTS public."ProjectRequirements" (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "ProjectId"  bigint NOT NULL REFERENCES public."Projects"(id) ON DELETE CASCADE,
  "DocType"    text   NOT NULL,   -- Contract | Karar | TeslimBelgesi | AlindiBelgesi | Fotograflar
  "Status"     text   NOT NULL DEFAULT 'Missing',
  "Notes"      text,
  UNIQUE ("ProjectId", "DocType")
);


-- ---------------------------------------------------------------------
-- 2. receipt_compliance  (payment-grain, computed -- never stored)
--    Receipt + Receipt-Translation from the auto-created Receipts row.
--    ELSE 'Missing' is the safe default: a NULL/absent receipt reads Missing.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW public.receipt_compliance AS
SELECT
    p.id           AS payment_id,
    p."ProjectId"  AS project_id,

    CASE
      WHEN r."Status" IN ('Received','Translated','Sent','Done') THEN 'Collected'
      WHEN r."Status" = 'Requested'                              THEN 'Requested'
      ELSE 'Missing'
    END AS receipt,

    CASE
      WHEN r."RequiresTranslation" = false      THEN 'Unnecessary'
      WHEN r."Status" = 'Done'                   THEN 'Collected'
      WHEN r."Status" IN ('Translated','Sent')   THEN 'Requested'
      ELSE 'Missing'
    END AS receipt_translation
FROM public."Payments" p
LEFT JOIN public."Receipts" r ON r."PaymentCode" = p.id;


-- ---------------------------------------------------------------------
-- 3. invoice_compliance  (project-grain, computed -- never stored)
--    Invoice slot = amount coverage: Collected when in-hand invoices
--    (Status >= Received) cover the project's non-returned payments.
--    Ungated/live: recomputed every read, so new spend re-opens a Collected.
--    Translation is gated on the invoice slot being Collected first.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW public.invoice_compliance AS
SELECT
    proj.id            AS project_id,
    proj."ProjectCode",
    agg.spend_to_document,
    agg.invoiced_in_hand,

    CASE
      WHEN agg.spend_to_document = 0                     THEN 'Missing'    -- no non-returned spend yet
      WHEN agg.invoiced_in_hand >= agg.spend_to_document THEN 'Collected'  -- every spent unit documented
      WHEN agg.has_activity                              THEN 'Requested'  -- invoices in flight but short
      ELSE 'Missing'                                                        -- spend exists, no invoices yet
    END AS invoice,

    CASE
      WHEN NOT agg.any_needs_translation                THEN 'Unnecessary'
      WHEN agg.spend_to_document > 0
           AND agg.invoiced_in_hand >= agg.spend_to_document   -- invoice slot is Collected
           AND agg.all_translations_done                THEN 'Collected'
      WHEN agg.any_translation_progress                 THEN 'Requested'
      ELSE 'Missing'
    END AS invoice_translation
FROM public."Projects" proj
CROSS JOIN LATERAL (
    SELECT
      -- money actually spent that needs documenting (returned payments excluded)
      COALESCE((SELECT SUM(pay."Amount") FROM public."Payments" pay
                WHERE pay."ProjectId" = proj.id
                  AND pay."Status" NOT IN ('Returned','Return-Closed')), 0) AS spend_to_document,
      -- invoices actually in hand (Received or later)
      COALESCE((SELECT SUM(inv."Amount") FROM public."Invoices" inv
                WHERE inv."ProjectCode" = proj."ProjectCode"
                  AND inv."Status" IN ('Received','Translated','Sent','Done')), 0) AS invoiced_in_hand,
      -- any invoice at all past Missing (drives the 'Requested' middle state)
      EXISTS (SELECT 1 FROM public."Invoices" inv
              WHERE inv."ProjectCode" = proj."ProjectCode"
                AND inv."Status" IN ('Requested','Received','Translated','Sent','Done')) AS has_activity,
      -- translation aggregates (weakest-link across translation-requiring invoices)
      EXISTS (SELECT 1 FROM public."Invoices" inv
              WHERE inv."ProjectCode" = proj."ProjectCode"
                AND inv."RequiresTranslation" = true) AS any_needs_translation,
      NOT EXISTS (SELECT 1 FROM public."Invoices" inv
                  WHERE inv."ProjectCode" = proj."ProjectCode"
                    AND inv."RequiresTranslation" = true
                    AND inv."Status" IS DISTINCT FROM 'Done') AS all_translations_done,
      EXISTS (SELECT 1 FROM public."Invoices" inv
              WHERE inv."ProjectCode" = proj."ProjectCode"
                AND inv."RequiresTranslation" = true
                AND inv."Status" IN ('Translated','Sent','Done')) AS any_translation_progress
) agg;


-- ---------------------------------------------------------------------
-- 4. compliance_report  (wide -- mirrors the legacy sheet, one row/payment)
--    Human slots pivoted from the two Requirements tables (absent -> Missing);
--    computed slots joined from the views (invoice by project, so it repeats
--    across a project's payment rows); Closed = AND of every slot.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW public.compliance_report AS
WITH base AS (
  SELECT
    p.id                                      AS payment_id,     -- for the edit path (route payment slots)
    p."ProjectId"                             AS project_id,     -- for the edit path (route project slots)
    p."PaymentCode"                           AS payment_code,
    s."CompanyName"                           AS organisation,
    p."PaymentDate"                           AS transfer_date,
    d."DecisionNumber"                        AS karar_no,
    p."Amount"                                AS amount,
    p."Currency"                              AS currency,

    COALESCE(preq.dekont,          'Missing') AS dekont,
    COALESCE(preq.transfer_order,  'Missing') AS transfer_order,
    COALESCE(projreq.contract,     'Missing') AS contract,

    ic.invoice                                AS invoice,   -- computed, project-grain
    ic.invoice_translation                    AS fatura,    -- computed
    rc.receipt                                AS receipt,   -- computed, payment-grain
    rc.receipt_translation                    AS makbuz,    -- computed

    COALESCE(preq.odeme_emri,        'Missing') AS odeme_emri,
    COALESCE(projreq.teslim_belgesi, 'Missing') AS teslim_belgesi,
    COALESCE(projreq.alindi_belgesi, 'Missing') AS alindi_belgesi,
    COALESCE(projreq.fotograflar,    'Missing') AS fotograflar,
    COALESCE(projreq.karar,          'Missing') AS karar
  FROM public."Payments" p
  LEFT JOIN public."Suppliers" s          ON s.id = p."SupplierId"
  LEFT JOIN public."Decisions" d          ON d.id = p."DecisionId"
  LEFT JOIN public.receipt_compliance rc  ON rc.payment_id = p.id
  LEFT JOIN public.invoice_compliance ic  ON ic.project_id = p."ProjectId"
  LEFT JOIN (
      SELECT "PaymentId",
        MAX("Status") FILTER (WHERE "DocType" = 'Dekont')        AS dekont,
        MAX("Status") FILTER (WHERE "DocType" = 'TransferOrder') AS transfer_order,
        MAX("Status") FILTER (WHERE "DocType" = 'OdemeEmri')     AS odeme_emri
      FROM public."PaymentRequirements" GROUP BY "PaymentId"
  ) preq ON preq."PaymentId" = p.id
  LEFT JOIN (
      SELECT "ProjectId",
        MAX("Status") FILTER (WHERE "DocType" = 'Contract')      AS contract,
        MAX("Status") FILTER (WHERE "DocType" = 'Karar')         AS karar,
        MAX("Status") FILTER (WHERE "DocType" = 'TeslimBelgesi') AS teslim_belgesi,
        MAX("Status") FILTER (WHERE "DocType" = 'AlindiBelgesi') AS alindi_belgesi,
        MAX("Status") FILTER (WHERE "DocType" = 'Fotograflar')   AS fotograflar
      FROM public."ProjectRequirements" GROUP BY "ProjectId"
  ) projreq ON projreq."ProjectId" = p."ProjectId"
)
SELECT base.*,
  CASE WHEN dekont          IN ('Collected','Unnecessary')
        AND transfer_order  IN ('Collected','Unnecessary')
        AND contract        IN ('Collected','Unnecessary')
        AND invoice         IN ('Collected','Unnecessary')
        AND fatura          IN ('Collected','Unnecessary')
        AND receipt         IN ('Collected','Unnecessary')
        AND makbuz          IN ('Collected','Unnecessary')
        AND odeme_emri      IN ('Collected','Unnecessary')
        AND teslim_belgesi  IN ('Collected','Unnecessary')
        AND alindi_belgesi  IN ('Collected','Unnecessary')
        AND fotograflar     IN ('Collected','Unnecessary')
        AND karar           IN ('Collected','Unnecessary')
       THEN 'Yes' ELSE 'No' END AS closed
FROM base;


-- ---------------------------------------------------------------------
-- 5. (Phase 5) expose the report to the PostgREST API so n8n can read it:
--      GRANT SELECT ON public.compliance_report TO anon, authenticated;
--    n8n then GETs /rest/v1/compliance_report?invoice=eq.Missing  (etc.)
-- ---------------------------------------------------------------------
