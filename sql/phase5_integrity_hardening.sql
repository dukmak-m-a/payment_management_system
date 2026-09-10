-- =====================================================================
-- Phase 5 — Compliance integrity hardening
-- NGO Compliance Tracking App
--
-- Run in the Supabase SQL editor AFTER sql/phase4_requirements.sql.
-- This migration is intentionally fail-closed: it refuses to apply when
-- existing data needs a human decision instead of silently changing it.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Preflight checks: stop before adding constraints if legacy records
--    would violate them. Inspect and repair the reported rows first.
-- ---------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public."Payments"
    WHERE "Status" IS NULL
       OR "Status" NOT IN ('Sent', 'Declared', 'Closed', 'Returned', 'Return-Closed')
       OR "Amount" IS NULL
       OR "Amount" < 0
       OR "Currency" IS NULL
       OR "Currency" NOT IN ('TRY', 'USD', 'EUR')
  ) THEN
    RAISE EXCEPTION
      'Payments contains a NULL/invalid Status or Currency, or a NULL/negative Amount. Repair those rows before rerunning this migration.';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public."Projects"
    WHERE "Currency" IS NULL
       OR "Currency" NOT IN ('TRY', 'USD', 'EUR')
  ) THEN
    RAISE EXCEPTION
      'Projects contains a NULL/invalid Currency. Repair those rows before rerunning this migration.';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public."Invoices"
    WHERE "Amount" < 0
       OR ("Status" IS NOT NULL AND "Status" NOT IN ('Missing', 'Requested', 'Received', 'Translated', 'Sent', 'Done'))
       OR ("Currency" IS NOT NULL AND "Currency" NOT IN ('TRY', 'USD', 'EUR'))
  ) THEN
    RAISE EXCEPTION
      'Invoices contains a negative Amount or invalid Status/Currency. Repair those rows before rerunning this migration.';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public."Receipts"
    WHERE "Amount" < 0
       OR ("Status" IS NOT NULL AND "Status" NOT IN ('Missing', 'Requested', 'Received', 'Translated', 'Sent', 'Done'))
  ) THEN
    RAISE EXCEPTION
      'Receipts contains a negative Amount or invalid Status. Repair those rows before rerunning this migration.';
  END IF;

  IF EXISTS (
    SELECT "PaymentCode"
    FROM public."Receipts"
    WHERE "PaymentCode" IS NOT NULL
    GROUP BY "PaymentCode"
    HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION
      'Receipts contains more than one row for a PaymentCode. Merge duplicates before rerunning this migration.';
  END IF;

  -- The report compares payment and invoice totals directly. It is only valid
  -- while each project has one currency. Receipts are intentionally excluded:
  -- a bank cut or commission can make their amount/currency legitimately differ.
  IF EXISTS (
    SELECT 1
    FROM public."Payments" pay
    JOIN public."Projects" proj ON proj.id = pay."ProjectId"
    WHERE pay."Currency" IS DISTINCT FROM proj."Currency"
  ) THEN
    RAISE EXCEPTION
      'Payments contains a Currency that does not match its Project. Repair those rows before rerunning this migration.';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public."Invoices" inv
    JOIN public."Projects" proj ON proj."ProjectCode" = inv."ProjectCode"
    WHERE inv."ProjectCode" IS NOT NULL
      AND inv."Currency" IS DISTINCT FROM proj."Currency"
  ) THEN
    RAISE EXCEPTION
      'Invoices contains a Currency that does not match its Project. Repair those rows before rerunning this migration.';
  END IF;
END $$;

-- A missing translation flag must fail toward requiring translation, never
-- toward Unnecessary. This backfill is safe because true is the conservative
-- state; the following NOT NULL constraints prevent recurrence.
UPDATE public."Invoices"
SET "RequiresTranslation" = true
WHERE "RequiresTranslation" IS NULL;

UPDATE public."Receipts"
SET "RequiresTranslation" = true
WHERE "RequiresTranslation" IS NULL;

-- Document Status = Missing is the safe representation of an absent status.
UPDATE public."Invoices" SET "Status" = 'Missing' WHERE "Status" IS NULL;
UPDATE public."Receipts" SET "Status" = 'Missing' WHERE "Status" IS NULL;

-- ---------------------------------------------------------------------
-- 2. Constraints: every compliance-view input is now explicit and valid.
-- ---------------------------------------------------------------------
ALTER TABLE public."Payments"
  ALTER COLUMN "Status" SET NOT NULL,
  ALTER COLUMN "Amount" SET NOT NULL,
  ALTER COLUMN "Currency" SET NOT NULL;

ALTER TABLE public."Projects"
  ALTER COLUMN "Currency" SET NOT NULL;

ALTER TABLE public."Invoices"
  ALTER COLUMN "Status" SET DEFAULT 'Missing',
  ALTER COLUMN "Status" SET NOT NULL,
  ALTER COLUMN "RequiresTranslation" SET DEFAULT true,
  ALTER COLUMN "RequiresTranslation" SET NOT NULL;

ALTER TABLE public."Receipts"
  ALTER COLUMN "Status" SET DEFAULT 'Missing',
  ALTER COLUMN "Status" SET NOT NULL,
  ALTER COLUMN "RequiresTranslation" SET DEFAULT true,
  ALTER COLUMN "RequiresTranslation" SET NOT NULL;

ALTER TABLE public."Payments"
  ADD CONSTRAINT "Payments_Status_check"
    CHECK ("Status" IN ('Sent', 'Declared', 'Closed', 'Returned', 'Return-Closed')),
  ADD CONSTRAINT "Payments_Amount_nonnegative_check"
    CHECK ("Amount" >= 0),
  ADD CONSTRAINT "Payments_Currency_check"
    CHECK ("Currency" IN ('TRY', 'USD', 'EUR'));

ALTER TABLE public."Invoices"
  ADD CONSTRAINT "Invoices_Status_check"
    CHECK ("Status" IN ('Missing', 'Requested', 'Received', 'Translated', 'Sent', 'Done')),
  ADD CONSTRAINT "Invoices_Amount_nonnegative_check"
    CHECK ("Amount" IS NULL OR "Amount" >= 0),
  ADD CONSTRAINT "Invoices_Currency_check"
    CHECK ("Currency" IS NULL OR "Currency" IN ('TRY', 'USD', 'EUR'));

ALTER TABLE public."Receipts"
  ADD CONSTRAINT "Receipts_Status_check"
    CHECK ("Status" IN ('Missing', 'Requested', 'Received', 'Translated', 'Sent', 'Done')),
  ADD CONSTRAINT "Receipts_Amount_nonnegative_check"
    CHECK ("Amount" IS NULL OR "Amount" >= 0),
  ADD CONSTRAINT "Receipts_PaymentCode_key" UNIQUE ("PaymentCode");

ALTER TABLE public."Projects"
  ADD CONSTRAINT "Projects_Budget_nonnegative_check"
    CHECK ("Budget" IS NULL OR "Budget" >= 0),
  ADD CONSTRAINT "Projects_Status_check"
    CHECK ("Status" IS NULL OR "Status" IN ('Active', 'Completed', 'On-Hold', 'Cancelled')),
  ADD CONSTRAINT "Projects_Currency_check"
    CHECK ("Currency" IN ('TRY', 'USD', 'EUR'));

ALTER TABLE public."PaymentRequirements"
  ADD CONSTRAINT "PaymentRequirements_Status_check"
    CHECK ("Status" IN ('Missing', 'Unnecessary', 'Requested', 'Collected')),
  ADD CONSTRAINT "PaymentRequirements_DocType_check"
    CHECK ("DocType" IN ('Dekont', 'TransferOrder', 'OdemeEmri'));

ALTER TABLE public."ProjectRequirements"
  ADD CONSTRAINT "ProjectRequirements_Status_check"
    CHECK ("Status" IN ('Missing', 'Unnecessary', 'Requested', 'Collected')),
  ADD CONSTRAINT "ProjectRequirements_DocType_check"
    CHECK ("DocType" IN ('Contract', 'Karar', 'TeslimBelgesi', 'AlindiBelgesi', 'Fotograflar'));

-- ---------------------------------------------------------------------
-- 3. Cross-table currency invariant. A CHECK constraint cannot read another
--    table, so triggers make the app's one-currency-per-project rule hold for
--    every writer: Flask, n8n, SQL editor, or future integrations.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.enforce_payment_project_currency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  project_currency text;
BEGIN
  SELECT "Currency" INTO project_currency
  FROM public."Projects"
  WHERE id = NEW."ProjectId";

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Selected project was not found';
  END IF;
  IF NEW."Currency" IS DISTINCT FROM project_currency THEN
    RAISE EXCEPTION 'Payment Currency must match the selected Project Currency';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_invoice_project_currency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  project_currency text;
BEGIN
  -- An unassigned draft invoice is allowed. Once assigned to a project, it
  -- must carry that project's currency before it can enter coverage math.
  IF NEW."ProjectCode" IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT "Currency" INTO project_currency
  FROM public."Projects"
  WHERE "ProjectCode" = NEW."ProjectCode";

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Selected project was not found';
  END IF;
  IF NEW."Currency" IS DISTINCT FROM project_currency THEN
    RAISE EXCEPTION 'Invoice Currency must match the selected Project Currency';
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_project_currency_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public."Payments"
    WHERE "ProjectId" = NEW.id
      AND "Currency" IS DISTINCT FROM NEW."Currency"
  ) OR EXISTS (
    SELECT 1 FROM public."Invoices"
    WHERE "ProjectCode" = NEW."ProjectCode"
      AND "Currency" IS DISTINCT FROM NEW."Currency"
  ) THEN
    RAISE EXCEPTION
      'Project Currency cannot change while related Payments or Invoices use a different Currency';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS "Payments_enforce_project_currency" ON public."Payments";
CREATE TRIGGER "Payments_enforce_project_currency"
  BEFORE INSERT OR UPDATE OF "ProjectId", "Currency" ON public."Payments"
  FOR EACH ROW EXECUTE FUNCTION public.enforce_payment_project_currency();

DROP TRIGGER IF EXISTS "Invoices_enforce_project_currency" ON public."Invoices";
CREATE TRIGGER "Invoices_enforce_project_currency"
  BEFORE INSERT OR UPDATE OF "ProjectCode", "Currency" ON public."Invoices"
  FOR EACH ROW EXECUTE FUNCTION public.enforce_invoice_project_currency();

DROP TRIGGER IF EXISTS "Projects_enforce_currency_change" ON public."Projects";
CREATE TRIGGER "Projects_enforce_currency_change"
  BEFORE UPDATE OF "Currency" ON public."Projects"
  FOR EACH ROW EXECUTE FUNCTION public.enforce_project_currency_change();

-- ---------------------------------------------------------------------
-- 4. One receipt is the model's intended grain. A payment's auto-created
--    receipt must be edited, not replaced by a second receipt row.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS "Invoices_ProjectCode_idx"
  ON public."Invoices" ("ProjectCode");
CREATE INDEX IF NOT EXISTS "Receipts_PaymentCode_idx"
  ON public."Receipts" ("PaymentCode");
CREATE INDEX IF NOT EXISTS "Payments_ProjectId_idx"
  ON public."Payments" ("ProjectId");
CREATE INDEX IF NOT EXISTS "Payments_SupplierId_idx"
  ON public."Payments" ("SupplierId");

COMMIT;

-- After a successful migration, re-run sql/phase4_requirements.sql so the
-- hardened view definitions become live as well.
