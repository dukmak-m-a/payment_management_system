# Payment Management System - Web Application

A full-stack web application for managing payments, projects, suppliers, donors, and decisions with a SQLite database backend.

## 📁 File Structure

```
payment-management/
├── app.py                      # Flask backend API
├── create_database.py          # Database setup script
├── requirements.txt            # Python dependencies
├── templates/
│   └── index.html             # Main HTML template
├── static/
│   ├── style.css              # CSS styling
│   └── app.js                 # Frontend JavaScript
└── payments_management.db     # SQLite database (created after setup)
```

## 🚀 Setup Instructions

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install Flask flask-cors
```

### Step 2: Create the Database

```bash
python create_database.py
```

This creates `payments_management.db` with all 5 tables:
- Donors
- Suppliers
- Decisions
- Projects
- Payments

### Step 3: Run the Application

```bash
python app.py
```

The server will start at: **http://localhost:5000**

## 💻 Usage

### Web Interface Features

1. **View Data**
   - Switch between tables using the navigation buttons
   - All records are displayed in a clean, searchable table

2. **Add New Records**
   - Click "Add New" button
   - Fill in the form fields
   - Click "Save"

3. **Edit Records**
   - Click "Edit" button on any row
   - Modify the fields
   - Click "Save"

4. **Delete Records**
   - Click "Delete" button on any row
   - Confirm deletion

5. **Search**
   - Use the search box to filter records in real-time

### API Endpoints

The Flask backend provides a RESTful API:

**GET all records:**
- `/api/donors`
- `/api/suppliers`
- `/api/decisions`
- `/api/projects`
- `/api/payments`

**POST new record:**
```bash
curl -X POST http://localhost:5000/api/suppliers \
  -H "Content-Type: application/json" \
  -d '{"CompanyName":"ABC Corp","Country":"USA"}'
```

**PUT update record:**
```bash
curl -X PUT http://localhost:5000/api/suppliers/1 \
  -H "Content-Type: application/json" \
  -d '{"CompanyName":"ABC Corporation","Country":"USA"}'
```

**DELETE record:**
```bash
curl -X DELETE http://localhost:5000/api/suppliers/1
```

## 🔗 Relationships

- **Projects** reference **Suppliers** (required) and **Donors** (optional)
- **Payments** reference **Suppliers**, **Projects** (both required), and **Donors**, **Decisions** (both optional)
- Foreign key constraints are enforced

## 📊 Database Schema

### Donors
- id (PRIMARY KEY)
- DonorCode (UNIQUE)
- DonorName
- Country
- ContactPerson

### Suppliers
- id (PRIMARY KEY)
- CompanyName
- Country
- ContactPerson
- TaxId (UNIQUE)

### Decisions
- id (PRIMARY KEY)
- DecisionNumber (UNIQUE)
- DecisionDate
- Description
- Attendants

### Projects
- id (PRIMARY KEY)
- ProjectCode (UNIQUE)
- Subject
- Description
- SupplierId (FK → Suppliers)
- DonorId (FK → Donors)
- Budget
- Currency
- StartDate
- EndDate
- Status (Active/Completed/Suspended/Cancelled)

### Payments
- id (PRIMARY KEY)
- SupplierId (FK → Suppliers)
- ProjectId (FK → Projects)
- DonorId (FK → Donors)
- DecisionId (FK → Decisions)
- Destination (Domestic/International)
- Kind (Receiving/Sending)
- Bank
- Amount
- Currency
- Status (Sent/Closed/Returned/Declared)
- PaymentDate
- DeclarationDate
- ClosingDate
- DaysToClose (computed: 90 - days since payment)

## 🎨 Design Features

- Modern, bold aesthetic with custom fonts
- Animated transitions and micro-interactions
- Color-coded status badges
- Responsive layout for mobile devices
- Dark theme with vibrant accents

## 🔧 Troubleshooting

**Database not found error:**
- Run `python create_database.py` first

**Port already in use:**
- Change the port in `app.py`: `app.run(port=5001)`

**Foreign key constraint errors:**
- Ensure referenced records exist before creating dependent records
- For example, create a Supplier before creating a Project

## 📝 Notes

- Dates must be in `YYYY-MM-DD` format
- All currency amounts support up to 2 decimal places
- The `DaysToClose` field is automatically calculated
- Records with foreign key references cannot be deleted until dependent records are removed first
