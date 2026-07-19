from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import date, datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
import os
import time


app = Flask(__name__)
load_dotenv()  # must run BEFORE any os.environ.get() below — .env isn't in the
               # environment until this loads it
# flask_cors removed 2026-07-19: the frontend is served same-origin by this app,
# and n8n calls server-to-server (CORS is a browser-only mechanism, it never
# blocked curl/n8n anyway). An open CORS policy combined with cookie auth would
# have let ANY website a logged-in user visits drive our API with their session.

# ============================================================
#  Session / auth configuration
# ============================================================
# Flask's session cookie is SIGNED with this key (itsdangerous), not encrypted:
# the browser can read what's inside, but cannot forge or alter it without the
# key. Never put secrets in the session — only identifiers.
_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
if not _SECRET_KEY:
    # Fail loudly rather than fall back to something guessable — a predictable
    # secret key lets anyone forge a logged-in session cookie.
    raise RuntimeError(
        "FLASK_SECRET_KEY is not set. Generate one with:\n"
        '  python -c "import secrets; print(secrets.token_hex(32))"\n'
        "and add it to .env"
    )
app.secret_key = _SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,     # JS cannot read the cookie (limits XSS -> session theft)
    SESSION_COOKIE_SAMESITE="Lax",    # cookie not sent on cross-site POSTs (baseline CSRF defence)
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # one workday, then re-login
    # SESSION_COOKIE_SECURE=True,     # VPS day: enable once behind HTTPS (breaks plain-HTTP local dev)
)

# ============================================================
#  Supabase connection
#  Set these in environment variables (or replace directly for testing)
# ============================================================
URL: str = os.environ.get("SUPABASE_URL")
KEY: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(URL, KEY)


# ============================================================
#  Helpers
# ============================================================

def _to_bool(value, default=True):
    """Coerce a form value to a real boolean for RequiresTranslation.

    A boolean column's DB DEFAULT only fires when the key is OMITTED from the
    INSERT — sending an explicit None writes NULL and overrides the default.
    The frontend serialises every field as a string (or null), so we normalise
    here and bias an absent/blank value to `default` (True). Risk asymmetry:
    assume a document needs translation unless someone explicitly opts out.
    """
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"true", "t", "yes", "1"}


# ============================================================
#  API Routes - GET
# ============================================================
 
@app.route('/api/donors', methods=['GET'])
def get_donors():
    try:
        res = supabase.table("Donors").select("*").order("DonorName").execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    try:
        res = supabase.table("Suppliers").select("*").order("CompanyName").execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route('/api/decisions', methods=['GET'])
def get_decisions():
    try:
        res = supabase.table("Decisions").select("*").order("DecisionDate", desc=True).execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route('/api/projects', methods=['GET'])
def get_projects():
    try:
        # Projects has NO DonorId — only SupplierId
        res = supabase.table("Projects").select(
            "*, Suppliers(CompanyName)"
        ).order("StartDate", desc=True).execute()
 
        projects = []
        for row in res.data:
            project = {k: v for k, v in row.items() if k != "Suppliers"}
            project["SupplierName"] = (row.get("Suppliers") or {}).get("CompanyName")
            projects.append(project)
 
        return jsonify(projects)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route('/api/payments', methods=['GET'])
def get_payments():
    try:
        res = supabase.table("Payments").select(
            "*, Suppliers(CompanyName), Projects(ProjectCode, Subject), Donors(DonorName), Decisions(DecisionNumber)"
        ).order("PaymentDate", desc=True).execute()
 
        today = date.today()
        payments = []
 
        for row in res.data:
            payment = {k: v for k, v in row.items()
                       if k not in ("Suppliers", "Projects", "Donors", "Decisions")}
 
            payment["SupplierName"]   = (row.get("Suppliers")  or {}).get("CompanyName")
            payment["ProjectCode"]    = (row.get("Projects")   or {}).get("ProjectCode")
            payment["ProjectSubject"] = (row.get("Projects")   or {}).get("Subject")
            payment["DonorName"]      = (row.get("Donors")     or {}).get("DonorName")
            payment["DecisionNumber"] = (row.get("Decisions")  or {}).get("DecisionNumber")
 
            # Calculate DaysToClose
            if payment.get("ClosingDate") or not payment.get("PaymentDate"):
                payment["DaysToClose"] = None
            else:
                try:
                    payment_date = datetime.strptime(payment["PaymentDate"], "%Y-%m-%d").date()
                    payment["DaysToClose"] = 90 - (today - payment_date).days
                except Exception:
                    payment["DaysToClose"] = None
 
            payments.append(payment)
 
        return jsonify(payments)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route('/api/receipts', methods=['GET'])
def get_receipts():
    try:
        res = supabase.table("Receipts").select(
            "*, Projects(Subject), Payments(Amount, Currency, PaymentCode)"
        ).order("ReceiptDate", desc=True).execute()

        receipts = []
        for row in res.data:
            receipt = {k: v for k, v in row.items()
                       if k not in ("Projects", "Payments")}
            receipt["ProjectSubject"]  = (row.get("Projects") or {}).get("Subject")
            receipt["PaymentAmount"]   = (row.get("Payments") or {}).get("Amount")
            receipt["PaymentCurrency"] = (row.get("Payments") or {}).get("Currency")
            receipt["PaymentCode"]     = (row.get("Payments") or {}).get("PaymentCode")
            receipts.append(receipt)

        return jsonify(receipts)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    try:
        res = supabase.table("Invoices").select(
            "*, Suppliers(CompanyName), Donors(DonorName), Projects(Subject)"
        ).order("Date", desc=True).execute()
 
        invoices = []
        for row in res.data:
            invoice = {k: v for k, v in row.items()
                       if k not in ("Suppliers", "Donors", "Projects")}
            invoice["SupplierName"]   = (row.get("Suppliers") or {}).get("CompanyName")
            invoice["DonorName"]      = (row.get("Donors")    or {}).get("DonorName")
            invoice["ProjectSubject"] = (row.get("Projects")  or {}).get("Subject")
            invoices.append(invoice)
 
        return jsonify(invoices)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
# ============================================================
#  API Routes - POST (Create)
# ============================================================
 
@app.route('/api/donors', methods=['POST'])
def create_donor():
    data = request.json
    try:
        res = supabase.table("Donors").insert({
            "DonorCode":     data["DonorCode"],
            "DonorName":     data["DonorName"],
            "Country":       data["Country"],
            "ContactPerson": data.get("ContactPerson"),
        }).execute()
        return jsonify({"success": True, "id": res.data[0]["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/suppliers', methods=['POST'])
def create_supplier():
    data = request.json
    try:
        res = supabase.table("Suppliers").insert({
            "CompanyName":   data["CompanyName"],
            "Country":       data["Country"],
            "ContactPerson": data.get("ContactPerson"),
        }).execute()
        return jsonify({"success": True, "id": res.data[0]["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/decisions', methods=['POST'])
def create_decision():
    data = request.json
    try:
        res = supabase.table("Decisions").insert({
            "DecisionNumber": data["DecisionNumber"],
            "DecisionDate":   data["DecisionDate"],
            "Description":    data.get("Description"),
            "Attendants":     data.get("Attendants"),
            "Notes":          data.get("Notes"),
        }).execute()
        return jsonify({"success": True, "id": res.data[0]["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.json
    try:
        res = supabase.table("Projects").insert({
            "ProjectCode":    data["ProjectCode"],
            "Subject":        data["Subject"],
            "Description":    data.get("Description"),
            "SupplierId":     data["SupplierId"],
            "Budget":         data.get("Budget"),
            "Currency":       data.get("Currency"),
            "StartDate":      data.get("StartDate"),
            "EndDate":        data.get("EndDate"),
            "Status":         data.get("Status", "Active"),
            "DriveFolderLink": data.get("DriveFolderLink"),
        }).execute()

        project_id = res.data[0]["id"]

        # Auto-create an invoice for the project — mirrors the auto-receipt on
        # payment. Invoices are project-grain, so one is created with the project.
        # Inherits Supplier/Currency; Amount left blank (officer fills it); Status
        # 'Missing' (under-claim); RequiresTranslation True (DB default / ~99% case).
        supabase.table("Invoices").insert({
            "ProjectCode":         data["ProjectCode"],
            "SupplierId":          data["SupplierId"],
            "Currency":            data.get("Currency"),
            "Status":              "Missing",
            "RequiresTranslation": True,
        }).execute()

        # Seed the project-grain compliance slots as Missing (under-claim).
        # These 5 are per-project — they repeat across the project's payments.
        supabase.table("ProjectRequirements").insert(
            [{"ProjectId": project_id, "DocType": dt, "Status": "Missing"}
             for dt in ("Contract", "Karar", "TeslimBelgesi",
                        "AlindiBelgesi", "Fotograflar")]
        ).execute()

        return jsonify({"success": True, "id": project_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/payments', methods=['POST'])
def create_payment():
    data = request.json
    try:
        # 1. Insert the payment
        res = supabase.table("Payments").insert({
            "PaymentCode":     data.get("PaymentCode"),
            "SupplierId":      data.get("SupplierId"),
            "Destination":     data.get("Destination"),
            "ProjectId":       data.get("ProjectId"),
            "DonorId":         data.get("DonorId"),
            "DecisionId":      data.get("DecisionId"),
            "Bank":            data.get("Bank"),
            "Amount":          data.get("Amount"),
            "Currency":        data.get("Currency"),
            "Status":          data.get("Status"),
            "DeclarationDate": data.get("DeclarationDate"),
            "PaymentDate":     data.get("PaymentDate"),
            "ClosingDate":     data.get("ClosingDate"),
        }).execute()

        payment = res.data[0]
        payment_id = payment["id"]           # numeric id — Receipts.PaymentCode is a BIGINT FK to this

        # 2. Resolve ProjectCode from ProjectId
        project_code = None
        if data.get("ProjectId"):
            proj = supabase.table("Projects").select("ProjectCode").eq("id", data["ProjectId"]).single().execute()
            project_code = proj.data.get("ProjectCode") if proj.data else None

        # 3. Auto-create receipt — inherits Project / Payment / Date / Amount / Currency from the payment.
        #    PaymentCode MUST be the numeric payment_id (BIGINT FK -> Payments.id), never the text code.
        supabase.table("Receipts").insert({
            "ProjectCode":         project_code,
            "PaymentCode":         payment_id,          # BIGINT FK -> Payments.id
            "PaymentDate":         data.get("PaymentDate"),
            "Amount":              data.get("Amount"),
            "Currency":            data.get("Currency"),
            "Status":              "Missing",           # under-claim: never auto-mark a receipt collected
            "RequiresTranslation": True,                # matches DB default; opting out is the rare case
        }).execute()

        # 4. Seed the payment-grain compliance slots as Missing (under-claim).
        #    The wide view COALESCEs an absent row to 'Missing' too, so this is
        #    materialization for editing, not a correctness dependency.
        supabase.table("PaymentRequirements").insert(
            [{"PaymentId": payment_id, "DocType": dt, "Status": "Missing"}
             for dt in ("Dekont", "TransferOrder", "OdemeEmri")]
        ).execute()

        return jsonify({"success": True, "id": payment_id})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/receipts', methods=['POST'])
def create_receipt():
    data = request.json
    try:
        res = supabase.table("Receipts").insert({
            "ProjectCode": data.get("ProjectCode"),
            "PaymentCode": data.get("PaymentCode"),
            "PaymentDate": data.get("PaymentDate"),
            "ReceiptCode": data.get("ReceiptCode"),
            "No":          data.get("No"),
            "ReceiptDate":        data.get("ReceiptDate"),
            "Amount":      data.get("Amount"),
            "Currency":    data.get("Currency"),
            "Status":      data.get("Status"),
            "RequiresTranslation": _to_bool(data.get("RequiresTranslation")),
            "AssignedTo":  data.get("AssignedTo"),
            "Notes":       data.get("Notes"),
        }).execute()
        return jsonify({"success": True, "id": res.data[0]["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/invoices', methods=['POST'])
def create_invoice():
    data = request.json
    try:
        res = supabase.table("Invoices").insert({
            "SupplierId":  data.get("SupplierId"),
            "DonorId":     data.get("DonorId"),
            "ProjectCode": data.get("ProjectCode"),
            "InvoiceCode": data.get("InvoiceCode"),
            "No":          data.get("No"),
            "Date":        data.get("Date"),
            "Amount":      data.get("Amount"),
            "Currency":    data.get("Currency"),
            "Status":      data.get("Status"),
            "RequiresTranslation": _to_bool(data.get("RequiresTranslation")),
            "AssignedTo":  data.get("AssignedTo"),
            "Notes":       data.get("Notes"),
        }).execute()
        return jsonify({"success": True, "id": res.data[0]["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
# ============================================================
#  API Routes - PUT (Update)
# ============================================================
 
@app.route('/api/donors/<int:id>', methods=['PUT'])
def update_donor(id):
    data = request.json
    try:
        supabase.table("Donors").update({
            "DonorCode":     data["DonorCode"],
            "DonorName":     data["DonorName"],
            "Country":       data["Country"],
            "ContactPerson": data.get("ContactPerson"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/suppliers/<int:id>', methods=['PUT'])
def update_supplier(id):
    data = request.json
    try:
        supabase.table("Suppliers").update({
            "CompanyName":   data["CompanyName"],
            "Country":       data["Country"],
            "ContactPerson": data.get("ContactPerson"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/decisions/<int:id>', methods=['PUT'])
def update_decision(id):
    data = request.json
    try:
        supabase.table("Decisions").update({
            "DecisionNumber": data["DecisionNumber"],
            "DecisionDate":   data["DecisionDate"],
            "Description":    data.get("Description"),
            "Attendants":     data.get("Attendants"),
            "Notes":          data.get("Notes"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/projects/<int:id>', methods=['PUT'])
def update_project(id):
    data = request.json
    try:
        supabase.table("Projects").update({
            "ProjectCode":    data["ProjectCode"],
            "Subject":        data["Subject"],
            "Description":    data.get("Description"),
            "SupplierId":     data["SupplierId"],
            "Budget":         data.get("Budget"),
            "Currency":       data.get("Currency"),
            "StartDate":      data.get("StartDate"),
            "EndDate":        data.get("EndDate"),
            "Status":         data.get("Status", "Active"),
            "DriveFolderLink": data.get("DriveFolderLink"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/payments/<int:id>', methods=['PUT'])
def update_payment(id):
    data = request.json
    try:
        supabase.table("Payments").update({
            "PaymentCode":     data.get("PaymentCode"),
            "SupplierId":      data.get("SupplierId"),
            "Destination":     data.get("Destination"),
            "ProjectId":       data.get("ProjectId"),
            "DonorId":         data.get("DonorId"),
            "DecisionId":      data.get("DecisionId"),
            "Bank":            data.get("Bank"),
            "Amount":          data.get("Amount"),
            "Currency":        data.get("Currency"),
            "Status":          data.get("Status"),
            "DeclarationDate": data.get("DeclarationDate"),
            "PaymentDate":     data.get("PaymentDate"),
            "ClosingDate":     data.get("ClosingDate"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/receipts/<int:id>', methods=['PUT'])
def update_receipt(id):
    data = request.json
    try:
        supabase.table("Receipts").update({
            "ProjectCode": data.get("ProjectCode"),
            "PaymentCode": data.get("PaymentCode"),
            "PaymentDate": data.get("PaymentDate"),
            "ReceiptCode": data.get("ReceiptCode"),
            "No":          data.get("No"),
            "ReceiptDate":        data.get("ReceiptDate"),
            "Amount":      data.get("Amount"),
            "Currency":    data.get("Currency"),
            "Status":      data.get("Status"),
            "RequiresTranslation": _to_bool(data.get("RequiresTranslation")),
            "AssignedTo":  data.get("AssignedTo"),
            "Notes":       data.get("Notes"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
@app.route('/api/invoices/<int:id>', methods=['PUT'])
def update_invoice(id):
    data = request.json
    try:
        supabase.table("Invoices").update({
            "SupplierId":  data.get("SupplierId"),
            "DonorId":     data.get("DonorId"),
            "ProjectCode": data.get("ProjectCode"),
            "InvoiceCode": data.get("InvoiceCode"),
            "No":          data.get("No"),
            "Date":        data.get("Date"),
            "Amount":      data.get("Amount"),
            "Currency":    data.get("Currency"),
            "Status":      data.get("Status"),
            "RequiresTranslation": _to_bool(data.get("RequiresTranslation")),
            "AssignedTo":  data.get("AssignedTo"),
            "Notes":       data.get("Notes"),
        }).eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
 
 
# ============================================================
#  Compliance report (Phase 4) — read the wide view, edit human slots
# ============================================================

@app.route('/api/compliance_report', methods=['GET'])
def get_compliance_report():
    try:
        res = (supabase.table("compliance_report")
               .select("*").order("transfer_date", desc=True).execute())
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# The four computed slots (invoice/fatura/receipt/makbuz) are intentionally NOT
# writable here — they live in the views and must never be hand-set (no manual
# override, ever). These allowlists enforce that: a payload naming a computed
# slot falls through to the 400 below, never reaching a table.
_PAYMENT_DOCS = {"Dekont", "TransferOrder", "OdemeEmri"}
_PROJECT_DOCS = {"Contract", "Karar", "TeslimBelgesi", "AlindiBelgesi", "Fotograflar"}
_SLOT_VALUES  = {"Missing", "Unnecessary", "Requested", "Collected"}


@app.route('/api/requirements', methods=['PUT'])
def upsert_requirement():
    """Set one human-edited compliance slot (insert-or-update on its unique key).

    Doubles as the backfill path: editing a slot on a pre-existing payment or
    project that was never seeded just inserts that one row; the others stay
    Missing via the view's COALESCE.
    """
    data     = request.json or {}
    scope    = data.get("scope")       # 'payment' or 'project'
    doc_type = data.get("doc_type")
    status   = data.get("status")
    owner_id = data.get("owner_id")    # Payments.id or Projects.id

    if status not in _SLOT_VALUES:
        return jsonify({"success": False, "error": "invalid status"}), 400
    if scope == "payment" and doc_type in _PAYMENT_DOCS:
        table, key = "PaymentRequirements", "PaymentId"
    elif scope == "project" and doc_type in _PROJECT_DOCS:
        table, key = "ProjectRequirements", "ProjectId"
    else:
        return jsonify({"success": False, "error": "invalid scope/doc_type"}), 400

    try:
        supabase.table(table).upsert(
            {key: owner_id, "DocType": doc_type, "Status": status},
            on_conflict=f"{key},DocType",
        ).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ============================================================
#  API Routes - DELETE
# ============================================================
 
@app.route('/api/<table>/<int:id>', methods=['DELETE'])
def delete_record(table, id):
    allowed_tables = ['Donors', 'Suppliers', 'Decisions', 'Projects', 'Payments', 'Receipts', 'Invoices']
    table = table.capitalize()
    if table not in allowed_tables:
        return jsonify({"success": False, "error": "Invalid table"}), 400
    try:
        supabase.table(table).delete().eq("id", id).execute()
        return jsonify({"success": True})
    except Exception as e:
        error_msg = str(e)
        if "foreign key" in error_msg.lower() or "violates" in error_msg.lower():
            return jsonify({"success": False, "error": "Cannot delete: record is referenced by other tables"}), 400
        return jsonify({"success": False, "error": error_msg}), 400
 
 
# ============================================================
#  Authentication
# ============================================================

# Hashing a fixed string once at startup gives us a real hash to check
# non-existent users against — so a login attempt takes the same time whether
# the username exists or not. Skipping the check for unknown users would let
# an attacker discover valid usernames by timing the responses.
_DUMMY_HASH = generate_password_hash("timing-equalizer-not-a-real-password")

# Brute-force throttle: per-username failure timestamps, in-process only.
# Good enough for local/single-worker; the real tool (Flask-Limiter, keyed by
# IP too, surviving restarts) is a VPS-day item.
_failed_logins = {}          # username -> [timestamps of recent failures]
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 15 * 60


def _too_many_failures(username):
    now = time.time()
    recent = [t for t in _failed_logins.get(username, []) if now - t < _LOCKOUT_SECONDS]
    _failed_logins[username] = recent
    return len(recent) >= _MAX_ATTEMPTS


@app.before_request
def require_login():
    """Default-deny guard: EVERY route requires a session unless allowlisted.

    Risk asymmetry applied to auth: a per-route @login_required decorator
    fails OPEN when you forget one (a silently unprotected route); a global
    default-deny fails CLOSED (a 401 someone notices immediately). Same
    principle as never letting a status silently look 'Done'.
    """
    if request.endpoint in ("login", "static"):
        return None
    if session.get("user_id"):
        return None
    # API callers (fetch/curl) get machine-readable 401; page visits get the login page.
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == 'GET':
        return render_template('login.html')

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if _too_many_failures(username):
        # 429 Too Many Requests; deliberately does NOT reveal whether the
        # account exists or the password was close.
        return render_template('login.html',
                               error="Too many failed attempts. Try again in 15 minutes."), 429

    account = None
    try:
        res = (supabase.table("Accounts")
               .select("id, Username, PasswordHash")
               .eq("Username", username)
               .eq("IsActive", True)
               .limit(1).execute())
        account = res.data[0] if res.data else None
    except Exception:
        account = None   # DB error -> fail closed: behaves like a bad login

    # Always run the hash check, even for unknown users (see _DUMMY_HASH).
    # check_password_hash compares in constant time — never compare with ==.
    stored_hash = account["PasswordHash"] if account else _DUMMY_HASH
    password_ok = check_password_hash(stored_hash, password)

    if not (account and password_ok):
        _failed_logins.setdefault(username, []).append(time.time())
        # ONE generic message for both wrong-username and wrong-password:
        # naming which one is wrong hands attackers a valid-username oracle.
        return render_template('login.html', error="Invalid username or password"), 401

    _failed_logins.pop(username, None)
    session.clear()              # session fixation: never reuse a pre-login session id
    session["user_id"] = account["id"]
    session["username"] = account["Username"]
    session.permanent = True     # apply PERMANENT_SESSION_LIFETIME (8h)
    return redirect(url_for("index"))


@app.route('/logout', methods=['POST'])   # POST, not GET: a GET link could be
def logout():                             # triggered cross-site or by prefetchers
    session.clear()
    return redirect(url_for("login"))


# ============================================================
#  Main route
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')
 
 
# ============================================================
#  Run
# ============================================================
 
if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Payment Management System")
    print("="*60)
    print(f"  ☁️  Database: Supabase ({URL})")
    print(f"  🌐 Server:   http://localhost:5000")
    print("="*60 + "\n")
 
    # VPS day: debug MUST be False in production — the Werkzeug debugger that
    # debug=True exposes on errors is an interactive Python console (= remote
    # code execution). Serve with gunicorn behind a reverse proxy instead.
    app.run(debug=True, host='0.0.0.0', port=5000)