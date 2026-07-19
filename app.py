from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import date, datetime
import os



app = Flask(__name__)
CORS(app)

# ============================================================
#  Supabase connection
#  Set these in environment variables (or replace directly for testing)
# ============================================================
load_dotenv()
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
        return jsonify({"success": True, "id": res.data[0]["id"]})
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
 
    app.run(debug=True, host='0.0.0.0', port=5000)