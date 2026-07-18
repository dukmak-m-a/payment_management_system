import sqlite3
import os

DB_PATH="Office_DB.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# TABLES = {

#     "Donors": """
#         CREATE TABLE IF NOT EXISTS Donors (
#             id            INTEGER  PRIMARY KEY AUTOINCREMENT,
#             DonorCode     TEXT     NOT NULL UNIQUE,
#             DonorName     TEXT     NOT NULL,
#             Country       TEXT     NOT NULL,
#             ContactPerson TEXT
#         );
#     """,

#     "Suppliers": """
#         CREATE TABLE IF NOT EXISTS Suppliers (
#             id            INTEGER  PRIMARY KEY AUTOINCREMENT,
#             CompanyName   TEXT     NOT NULL,
#             ContactPerson TEXT,
#             Country       TEXT     NOT NULL,
#             TaxId         TEXT     UNIQUE
#         );
#     """,

#     "Decisions": """
#         CREATE TABLE IF NOT EXISTS Decisions (
#             id             INTEGER  PRIMARY KEY AUTOINCREMENT,
#             DecisionNumber TEXT     NOT NULL UNIQUE,
#             DecisionDate   DATE     NOT NULL,
#             Description    TEXT,
#             Attendants     TEXT
#         );
#     """,

#     "Projects": """
#         CREATE TABLE IF NOT EXISTS Projects (
#             id            INTEGER  PRIMARY KEY AUTOINCREMENT,
#             ProjectCode   TEXT     NOT NULL UNIQUE,
#             Subject       TEXT     NOT NULL,
#             Description   TEXT,
#             SupplierId    INTEGER  NOT NULL  REFERENCES Suppliers(id),
#             DonorId       INTEGER            REFERENCES Donors(id),
#             Budget        REAL     NOT NULL,
#             Currency      TEXT     NOT NULL,
#             StartDate     DATE     NOT NULL,
#             EndDate       DATE     NOT NULL,
#             Status        TEXT     NOT NULL  DEFAULT 'Active'
#                           CHECK (Status IN ('Active', 'Completed', 'Suspended', 'Cancelled'))
#         );
#     """,

#     "Payments": """
#         CREATE TABLE IF NOT EXISTS Payments (
#             id              INTEGER  PRIMARY KEY AUTOINCREMENT,
#             SupplierId      INTEGER  NOT NULL  REFERENCES Suppliers(id),
#             Destination     TEXT     NOT NULL
#                             CHECK (Destination IN ('Domestic', 'International')),
#             Kind            TEXT     NOT NULL
#                             CHECK (Kind IN ('Receiving', 'Sending')),
#             ProjectId       INTEGER  NOT NULL  REFERENCES Projects(id),
#             DonorId         INTEGER            REFERENCES Donors(id),
#             DecisionId      INTEGER            REFERENCES Decisions(id),
#             Bank            TEXT     NOT NULL,
#             Amount          REAL     NOT NULL,
#             Currency        TEXT     NOT NULL,
#             Status          TEXT     NOT NULL
#                             CHECK (Status IN ('Sent', 'Closed', 'Returned', 'Declared')),
#             DeclarationDate DATE,
#             PaymentDate     DATE     NOT NULL,
#             ClosingDate     DATE,
#             DaysToClose     INTEGER  GENERATED ALWAYS AS (
#                                 CASE
#                                     WHEN ClosingDate IS NOT NULL THEN NULL
#                                     ELSE 90 - CAST(
#                                         julianday(DATE('now')) - julianday(PaymentDate)
#                                     AS INTEGER)
#                                 END
#                             ) VIRTUAL
#         );
#     """,
# }


# INDEXES = [
#     "CREATE INDEX IF NOT EXISTS idx_suppliers_country      ON Suppliers (Country);",
#     "CREATE INDEX IF NOT EXISTS idx_donors_country         ON Donors (Country);",
#     "CREATE INDEX IF NOT EXISTS idx_decisions_number       ON Decisions (DecisionNumber);",
#     "CREATE INDEX IF NOT EXISTS idx_projects_supplier      ON Projects (SupplierId);",
#     "CREATE INDEX IF NOT EXISTS idx_projects_donor         ON Projects (DonorId);",
#     "CREATE INDEX IF NOT EXISTS idx_projects_status        ON Projects (Status);",
#     "CREATE INDEX IF NOT EXISTS idx_projects_code          ON Projects (ProjectCode);",
#     "CREATE INDEX IF NOT EXISTS idx_payments_supplier      ON Payments (SupplierId);",
#     "CREATE INDEX IF NOT EXISTS idx_payments_project       ON Payments (ProjectId);",
#     "CREATE INDEX IF NOT EXISTS idx_payments_donor         ON Payments (DonorId);",
#     "CREATE INDEX IF NOT EXISTS idx_payments_decision      ON Payments (DecisionId);",
#     "CREATE INDEX IF NOT EXISTS idx_payments_status        ON Payments (Status);",
#     "CREATE INDEX IF NOT EXISTS idx_payments_payment_date  ON Payments (PaymentDate);",
# ]

# def create_tables(conn):
#     cursor = conn.cursor()
#     for table_name, sql in TABLES.items():
#         cursor.execute(sql)
#         print(f"  ✔ Table '{table_name}' ready")
#     for sql in INDEXES:
#         cursor.execute(sql)
#     conn.commit()
#     print("  ✔ All indexes created")


def add_donor(conn, donor_code, donor_name, country, contact_person=None):
    sql = """
        INSERT INTO Donors (DonorCode, DonorName, Country, ContactPerson)
        VALUES (?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (donor_code, donor_name, country, contact_person))
    conn.commit()
    return cursor.lastrowid


def add_supplier(conn, company_name, country, contact_person=None, tax_id=None):
    sql = """
        INSERT INTO Suppliers (CompanyName, Country, ContactPerson, TaxId)
        VALUES (?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (company_name, country, contact_person, tax_id))
    conn.commit()
    return cursor.lastrowid


def add_decision(conn, decision_number, decision_date, description=None, attendants=None):
    sql = """
        INSERT INTO Decisions (DecisionNumber, DecisionDate, Description, Attendants)
        VALUES (?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (decision_number, decision_date, description, attendants))
    conn.commit()
    return cursor.lastrowid


def add_project(conn, project_code, subject, supplier_id, budget, currency,
                start_date, end_date, description=None, donor_id=None, status='Active'):
    sql = """
        INSERT INTO Projects (ProjectCode, Subject, Description, SupplierId,
                              DonorId, Budget, Currency, StartDate, EndDate, Status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (project_code, subject, description, supplier_id,
                         donor_id, budget, currency, start_date, end_date, status))
    conn.commit()
    return cursor.lastrowid


def add_payment(conn, supplier_id, destination, kind, project_id, bank, amount,
                currency, status, payment_date, donor_id=None, decision_id=None,
                declaration_date=None, closing_date=None):
    sql = """
        INSERT INTO Payments (SupplierId, Destination, Kind, ProjectId, DonorId,
                              DecisionId, Bank, Amount, Currency, Status,
                              DeclarationDate, PaymentDate, ClosingDate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (supplier_id, destination, kind, project_id, donor_id,
                         decision_id, bank, amount, currency, status,
                         declaration_date, payment_date, closing_date))
    conn.commit()
    return cursor.lastrowid

def get_all(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    cols = [description[0] for description in cursor.description]
    return cols, rows


def get_payments_full(conn):
    """Returns payments joined with supplier, project, donor and decision names."""
    sql = """
        SELECT
            p.id,
            s.CompanyName     AS Supplier,
            p.Destination,
            p.Kind,
            pr.ProjectCode    AS Project,
            d.DonorName       AS Donor,
            dc.DecisionNumber AS Decision,
            p.Bank,
            p.Amount,
            p.Currency,
            p.Status,
            p.DeclarationDate,
            p.PaymentDate,
            p.ClosingDate,
            p.DaysToClose
        FROM Payments p
        JOIN  Suppliers s   ON s.id  = p.SupplierId
        JOIN  Projects  pr  ON pr.id = p.ProjectId
        LEFT  JOIN Donors   d  ON d.id  = p.DonorId
        LEFT  JOIN Decisions dc ON dc.id = p.DecisionId
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    cols = [description[0] for description in cursor.description]
    return cols, rows


# ============================================================
#  Main — run to initialize the database
# ============================================================

if __name__ == "__main__":
    # print(f"\n{'='*50}")
    # print(f"  Setting up database: {DB_PATH}")
    # print(f"{'='*50}")

    # conn = get_connection()
    # create_tables(conn)


    # print(f"\n  ✔ Database created successfully at: {os.path.abspath(DB_PATH)}")
    # print(f"{'='*50}\n")

    conn = get_connection()

    donor_id    = add_donor(conn, "DON001", "UN Agency", "USA", "John Smith")
    supplier_id = add_supplier(conn, "ABC Construction", "Afghanistan", "Ahmad Karimi")
    decision_id = add_decision(conn, "DEC-2024-01", "2024-01-15", "Board approval", "Ali, Sara, John")
    project_id  = add_project(conn, "PRJ-2024-01", "Road Construction", supplier_id,
                            500000, "USD", "2024-02-01", "2024-12-31", donor_id=donor_id)
    add_payment(conn, supplier_id, "International", "Sending", project_id,
                "Kabul Bank", 50000, "USD", "Sent", "2024-03-01",
                donor_id=donor_id, decision_id=decision_id)

    conn.close()



