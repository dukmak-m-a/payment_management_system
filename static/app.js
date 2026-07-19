// ============================================================
//  Global State
// ============================================================

let currentTable = 'payments';
let currentData = [];
let editingId = null;
let lookupData = {
    suppliers: [],
    donors: [],
    projects: [],
    decisions: [],
    payments: []
};
let columnOrders = {};

// ============================================================
//  Table Definitions
// ============================================================

const tableConfigs = {
    payments: {
        name: 'Payments',
        columns: ['id', 'PaymentCode', 'SupplierName', 'ProjectCode', 'DonorName',
                  'DecisionNumber', 'Destination', 'Bank', 'Amount', 'Currency',
                  'Status', 'PaymentDate', 'DaysToClose', 'DeclarationDate', 'ClosingDate'],
        displayNames: {
            'id': 'ID',
            'PaymentCode': 'Payment Code',
            'SupplierName': 'Supplier',
            'ProjectCode': 'Project',
            'DonorName': 'Donor',
            'DecisionNumber': 'Decision',
            'Destination': 'Destination',
            'Bank': 'Bank',
            'Amount': 'Amount',
            'Currency': 'Currency',
            'Status': 'Status',
            'PaymentDate': 'Payment Date',
            'DaysToClose': 'Days to Close',
            'DeclarationDate':'Declaration Date',
            'ClosingDate': 'Closing Date'
        },
        formFields: [
    { name: 'PaymentCode', label: 'Payment Code', type: 'text', required: false },
    { name: 'SupplierId', label: 'Supplier', type: 'select', required: true, lookup: 'suppliers' },
    { name: 'ProjectId', label: 'Project', type: 'select', required: true, lookup: 'projects' },
    { name: 'DonorId', label: 'Donor', type: 'select', required: false, lookup: 'donors' },
    { name: 'DecisionId', label: 'Decision', type: 'select', required: true, lookup: 'decisions' },
    { name: 'Destination', label: 'Destination', type: 'select', required: true,
      options: ['Domestic', 'International'] },
    { name: 'Bank', label: 'Bank', type: 'select', required: false, 
      options: ['Türkiye Vakıflar Bankası', 'Ziraat Katılım Bankası', 'Albaraka Türk Katılım Bankası'] },
    { name: 'Amount', label: 'Amount', type: 'number', required: true, step: '0.01' },
    { name: 'Currency', label: 'Currency', type: 'select', required: true,
      options: ['TRY', 'USD', 'EUR'] },
    { name: 'Status', label: 'Status', type: 'select', required: true,
      options: ['Sent', 'Declared', 'Closed', 'Returned', 'Return-Closed'] },
    { name: 'PaymentDate', label: 'Payment Date', type: 'date', required: true },
    { name: 'DeclarationDate', label: 'Declaration Date', type: 'date', required: true },
    { name: 'ClosingDate', label: 'Closing Date', type: 'date', required: false }
    // ReceiptCode removed
]
    },
    projects: {
        name: 'Projects',
        columns: ['id', 'ProjectCode', 'Subject','Description', 'SupplierName', 'Budget',
                  'Currency', 'StartDate', 'EndDate', 'Status', 'DriveFolderLink'],
        displayNames: {
            'id': 'ID',
            'ProjectCode': 'Code',
            'Subject': 'Subject',
            'Description': 'Description',
            'SupplierName': 'Supplier',
            'Budget': 'Budget',
            'Currency': 'Currency',
            'StartDate': 'Start Date',
            'EndDate': 'End Date',
            'Status': 'Status',
            'DriveFolderLink': 'Drive Folder'
        },
        formFields: [
            { name: 'ProjectCode', label: 'Project Code', type: 'text', required: true },
            { name: 'Subject', label: 'Subject', type: 'text', required: true },
            { name: 'Description', label: 'Description', type: 'textarea', required: false },
            { name: 'SupplierId', label: 'Supplier', type: 'select', required: true, lookup: 'suppliers' },
            { name: 'Budget', label: 'Budget', type: 'number', required: true, step: '0.01' },
            { name: 'Currency', label: 'Currency', type: 'select', required: true, options: ['TRY', 'USD', 'EUR'] },
            { name: 'StartDate', label: 'Start Date', type: 'date', required: true },
            { name: 'EndDate', label: 'End Date', type: 'date', required: true },
            { name: 'Status', label: 'Status', type: 'select', required: true,
              options: ['Active', 'Completed', 'On-Hold', 'Cancelled'] },
            { name: 'DriveFolderLink', label: 'Drive Folder Link', type: 'text', required: false }
        ]
    },
    invoices: {
        name: 'Invoices',
        columns: ['id', 'InvoiceCode', 'No', 'SupplierName', 'DonorName',
                  'ProjectCode', 'Date', 'Amount', 'Currency', 'Status',
                  'RequiresTranslation', 'AssignedTo', 'Notes'],
        displayNames: {
            'id': 'ID',
            'InvoiceCode': 'Invoice Code',
            'No': 'No.',
            'SupplierName': 'Supplier',
            'DonorName': 'Donor',
            'ProjectCode': 'Project',
            'Date': 'Date',
            'Amount': 'Amount',
            'Currency': 'Currency',
            'Status': 'Status',
            'RequiresTranslation': 'Translation?',
            'AssignedTo': 'Assigned To',
            'Notes': 'Notes'
        },
        formFields: [
            { name: 'InvoiceCode', label: 'Invoice Code', type: 'text', required: false },
            { name: 'No', label: 'No.', type: 'text', required: false },
            { name: 'SupplierId', label: 'Supplier', type: 'select', required: false, lookup: 'suppliers' },
            { name: 'DonorId', label: 'Donor', type: 'select', required: false, lookup: 'donors' },
            { name: 'ProjectCode', label: 'Project', type: 'select', required: false, lookup: 'projectsByCode' },
            { name: 'Date', label: 'Date', type: 'date', required: false },
            { name: 'Amount', label: 'Amount', type: 'number', required: false, step: '0.01' },
            { name: 'Currency', label: 'Currency', type: 'select', required: false, options: ['TRY', 'USD', 'EUR'] },
            { name: 'Status', label: 'Status', type: 'select', required: false,
              options: ['Missing', 'Requested', 'Received', 'Translated', 'Sent', 'Done'] },
            { name: 'RequiresTranslation', label: 'Requires Translation', type: 'select', required: true,
              options: ['true', 'false'] },
            { name: 'AssignedTo', label: 'Assigned To', type: 'text', required: false },
            { name: 'Notes', label: 'Notes', type: 'textarea', required: false }
        ]
    },
    receipts: {
        name: 'Receipts',
        columns: ['id', 'ReceiptCode', 'No', 'ProjectCode', 'PaymentCode',
              'PaymentDate', 'ReceiptDate', 'Amount', 'Currency', 'Status',
              'RequiresTranslation', 'AssignedTo', 'Notes'],
        displayNames: {
            'id': 'ID',
            'ReceiptCode': 'Receipt Code',
            'No': 'No.',
            'ProjectCode': 'Project',
            'PaymentCode': 'Payment Code',   // ← changed from 'Payment'
            'PaymentDate': 'Payment Date',
            'ReceiptDate': 'Receipt Date',
            'Amount': 'Amount',
            'Currency': 'Currency',
            'Status': 'Status',
            'RequiresTranslation': 'Translation?',
            'AssignedTo': 'Assigned To',
            'Notes': 'Notes'
        },
        formFields: [
            { name: 'ReceiptCode', label: 'Receipt Code', type: 'text', required: false },
            { name: 'No', label: 'No.', type: 'text', required: false },
            { name: 'ProjectCode', label: 'Project', type: 'select', required: false, lookup: 'projectsByCode' },
            { name: 'PaymentCode', label: 'Payment', type: 'select', required: false, lookup: 'payments' },
            { name: 'PaymentDate', label: 'Payment Date', type: 'date', required: false },
            { name: 'ReceiptDate', label: 'Receipt Date', type: 'date', required: false },
            { name: 'Amount', label: 'Amount', type: 'number', required: false, step: '0.01' },
            { name: 'Currency', label: 'Currency', type: 'select', required: true, options: ['TRY', 'USD', 'EUR'] },
            { name: 'Status', label: 'Status', type: 'select', required: false,
              options: ['Missing', 'Requested', 'Received', 'Translated', 'Sent', 'Done'] },
            { name: 'RequiresTranslation', label: 'Requires Translation', type: 'select', required: true,
              options: ['true', 'false'] },
            { name: 'AssignedTo', label: 'Assigned To', type: 'text', required: false },
            { name: 'Notes', label: 'Notes', type: 'textarea', required: false }
        ]
    },
    suppliers: {
        name: 'Suppliers',
        columns: ['id', 'CompanyName', 'Country', 'ContactPerson'],
        displayNames: {
            'id': 'ID',
            'CompanyName': 'Company Name',
            'Country': 'Country',
            'ContactPerson': 'Contact Person'
        },
        formFields: [
            { name: 'CompanyName', label: 'Company Name', type: 'text', required: true },
            { name: 'Country', label: 'Country', type: 'text', required: true },
            { name: 'ContactPerson', label: 'Contact Person', type: 'text', required: false }
        ]
    },
    donors: {
        name: 'Donors',
        columns: ['id', 'DonorCode', 'DonorName', 'Country', 'ContactPerson'],
        displayNames: {
            'id': 'ID',
            'DonorCode': 'Code',
            'DonorName': 'Donor Name',
            'Country': 'Country',
            'ContactPerson': 'Contact Person'
        },
        formFields: [
            { name: 'DonorCode', label: 'Donor Code', type: 'text', required: true },
            { name: 'DonorName', label: 'Donor Name', type: 'text', required: true },
            { name: 'Country', label: 'Country', type: 'text', required: true },
            { name: 'ContactPerson', label: 'Contact Person', type: 'text', required: false }
        ]
    },
    decisions: {
        name: 'Decisions',
        columns: ['id', 'DecisionNumber', 'DecisionDate', 'Description', 'Attendants', 'Notes'],
        displayNames: {
            'id': 'ID',
            'DecisionNumber': 'Decision Number',
            'DecisionDate': 'Decision Date',
            'Description': 'Description',
            'Attendants': 'Attendants',
            'Notes': 'Notes'
        },
        formFields: [
            { name: 'DecisionNumber', label: 'Decision Number', type: 'text', required: true },
            { name: 'DecisionDate', label: 'Decision Date', type: 'date', required: true },
            { name: 'Description', label: 'Description', type: 'textarea', required: false },
            { name: 'Attendants', label: 'Attendants', type: 'text', required: false },
            { name: 'Notes', label: 'Notes', type: 'textarea', required: false }
        ]
    }
};

// ============================================================
//  Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
    loadColumnOrders();
    await loadLookupData();
    await loadData();
    setupEventListeners();
});

// ============================================================
//  Event Listeners
// ============================================================

function setupEventListeners() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentTable = e.target.dataset.table;
            await loadData();
        });
    });

    document.getElementById('addNewBtn').addEventListener('click', () => openModal());
    document.getElementById('columnSettingsBtn').addEventListener('click', () => openColumnSettings());
    document.getElementById('closeModal').addEventListener('click', closeModal);
    document.getElementById('cancelBtn').addEventListener('click', closeModal);
    document.getElementById('closeColumnModal').addEventListener('click', closeColumnModal);
    document.getElementById('saveColumnsBtn').addEventListener('click', saveColumnOrder);
    document.getElementById('resetColumnsBtn').addEventListener('click', resetColumnOrder);
    document.getElementById('recordForm').addEventListener('submit', handleFormSubmit);
    document.getElementById('searchInput').addEventListener('input', handleSearch);

    document.getElementById('modal').addEventListener('click', (e) => {
        if (e.target.id === 'modal') closeModal();
    });
    document.getElementById('columnModal').addEventListener('click', (e) => {
        if (e.target.id === 'columnModal') closeColumnModal();
    });
}

// ============================================================
//  Data Loading
// ============================================================

async function loadLookupData() {
    try {
        // Load sequentially, NOT with Promise.all. The Flask dev server shares one
        // global Supabase client that isn't safe for concurrent use — firing all five
        // at once collides on its socket and throws EAGAIN ([Errno 11]). One request
        // in flight at a time avoids the collision. (Real backend concurrency-safety —
        // needed once n8n hits the API alongside the UI — is a Phase 5 task.)
        const suppliers = await fetch('/api/suppliers').then(r => r.json());
        const donors    = await fetch('/api/donors').then(r => r.json());
        const projects  = await fetch('/api/projects').then(r => r.json());
        const decisions = await fetch('/api/decisions').then(r => r.json());
        const payments  = await fetch('/api/payments').then(r => r.json());
        lookupData = { suppliers, donors, projects, decisions, payments };
    } catch (error) {
        console.error('Error loading lookup data:', error);
        showNotification('Error loading reference data', 'error');
    }
}

async function loadData() {
    showLoading(true);
    try {
        const response = await fetch(`/api/${currentTable}`);
        currentData = await response.json();
        renderTable();
    } catch (error) {
        console.error('Error loading data:', error);
        showNotification('Error loading data', 'error');
    } finally {
        showLoading(false);
    }
}

// ============================================================
//  Column Order Management
// ============================================================

function loadColumnOrders() {
    const stored = localStorage.getItem('columnOrders');
    if (stored) columnOrders = JSON.parse(stored);
}

function saveColumnOrders() {
    localStorage.setItem('columnOrders', JSON.stringify(columnOrders));
}

function getColumnOrder(table) {
    return columnOrders[table] || tableConfigs[table].columns;
}

function openColumnSettings() {
    const config = tableConfigs[currentTable];
    const currentOrder = getColumnOrder(currentTable);
    const columnList = document.getElementById('columnList');

    columnList.innerHTML = currentOrder
        .filter(col => col !== 'id')
        .map(col => `
            <li class="column-item" draggable="true" data-column="${col}">
                <span class="column-drag-handle">☰</span>
                <span class="column-name">${config.displayNames[col] || col}</span>
            </li>
        `).join('');

    setupColumnDragAndDrop();
    document.getElementById('columnModal').classList.add('show');
}

function closeColumnModal() {
    document.getElementById('columnModal').classList.remove('show');
}

function setupColumnDragAndDrop() {
    const columnList = document.getElementById('columnList');
    let draggedItem = null;

    columnList.querySelectorAll('.column-item').forEach(item => {
        item.addEventListener('dragstart', () => {
            draggedItem = item;
            item.classList.add('dragging');
        });
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
        });
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            const afterElement = getDragAfterElement(columnList, e.clientY);
            if (afterElement == null) {
                columnList.appendChild(draggedItem);
            } else {
                columnList.insertBefore(draggedItem, afterElement);
            }
        });
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.column-item:not(.dragging)')];
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function saveColumnOrder() {
    const columnList = document.getElementById('columnList');
    const items = columnList.querySelectorAll('.column-item');
    const newOrder = ['id'];
    items.forEach(item => newOrder.push(item.dataset.column));
    columnOrders[currentTable] = newOrder;
    saveColumnOrders();
    closeColumnModal();
    renderTable();
    showNotification('Column order saved', 'success');
}

function resetColumnOrder() {
    delete columnOrders[currentTable];
    saveColumnOrders();
    closeColumnModal();
    renderTable();
    showNotification('Column order reset to default', 'success');
}

// ============================================================
//  Table Rendering
// ============================================================

function renderTable() {
    const config = tableConfigs[currentTable];
    const columns = getColumnOrder(currentTable);
    const thead = document.getElementById('tableHead');
    const tbody = document.getElementById('tableBody');

    thead.innerHTML = `
        <tr>
            ${columns.map(col => `<th>${config.displayNames[col] || col}</th>`).join('')}
            <th>Actions</th>
        </tr>
    `;

    if (currentData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="${columns.length + 1}" style="text-align: center; padding: 3rem;">
                    No records found
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = currentData.map(row => `
        <tr>
            ${columns.map(col => `<td>${formatCell(col, row[col])}</td>`).join('')}
            <td>
                <div class="action-btns">
                    <button class="btn-details" onclick="viewDetails(${row.id})">More Details</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function formatCell(column, value) {
    if (value === null || value === undefined) {
        return '<span style="color: #666;">—</span>';
    }

    if (column === 'Status') {
        const statusClass = 'status-' + value.toLowerCase().replace(/\s+/g, '-');
        return `<span class="status-badge ${statusClass}">${value}</span>`;
    }

    if (column === 'Amount' || column === 'Budget') {
        return parseFloat(value).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    if (column === 'DaysToClose') {
        const num = parseInt(value);
        let color = '#06D6A0';
        if (num < 30) color = '#FFD23F';
        if (num < 10) color = '#EF476F';
        return `<span style="color: ${color}; font-weight: 700;">${num} days</span>`;
    }

    // Render Drive folder links as clickable icons
    if (column === 'DriveFolderLink') {
        return `<a href="${value}" target="_blank" rel="noopener noreferrer" 
                   style="color: var(--accent); text-decoration: none; font-size: 1.2rem;" 
                   title="Open Drive Folder">📁</a>`;
    }

    return value;
}

// ============================================================
//  Modal
// ============================================================

function openModal(id = null) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modalTitle');
    const formFields = document.getElementById('formFields');

    editingId = id;
    modalTitle.textContent = id ? 'Edit Record' : 'Add New ${tableName}'.replace('${tableName}', tableConfigs[currentTable].name);

    const config = tableConfigs[currentTable];
    formFields.innerHTML = config.formFields.map(field => `
        <div class="form-group">
            <label for="${field.name}">
                ${field.label}${field.required ? ' *' : ''}
            </label>
            ${renderFormField(field)}
        </div>
    `).join('');

    if (id) {
        const record = currentData.find(r => r.id === id);
        if (record) {
            config.formFields.forEach(field => {
                const input = document.getElementById(field.name);
                if (input && record[field.name] !== undefined) {
                    // Use ?? not || : || also blanks falsy-but-real values (false, 0),
                    // silently turning a stored `false`/`0` into an empty field on edit.
                    input.value = record[field.name] ?? '';
                }
            });
        }
    }

    modal.classList.add('show');
    document.querySelector('.modal-actions').style.display = 'flex';
}

function renderFormField(field) {
    if (field.type === 'select') {
        let options = '';

        if (field.lookup) {
            const data = lookupData[field.lookup];
            options = `<option value="">-- Select ${field.label} --</option>`;

            if (field.lookup === 'suppliers') {
                options += data.map(item =>
                    `<option value="${item.id}">${item.CompanyName}</option>`
                ).join('');
            } else if (field.lookup === 'donors') {
                options += data.map(item =>
                    `<option value="${item.id}">${item.DonorName}</option>`
                ).join('');
            } else if (field.lookup === 'projects') {
                options += data.map(item =>
                    `<option value="${item.id}">${item.ProjectCode} - ${item.Subject}</option>`
                ).join('');
            } else if (field.lookup === 'projectsByCode') {
                // Use ProjectCode as value (for Receipts & Invoices foreign key)
                options += lookupData.projects.map(item =>
                    `<option value="${item.ProjectCode}">${item.ProjectCode} - ${item.Subject}</option>`
                ).join('');
            } else if (field.lookup === 'decisions') {
                options += data.map(item =>
                    `<option value="${item.id}">${item.DecisionNumber}</option>`
                ).join('');
            } else if (field.lookup === 'payments') {
                // PaymentCode foreign key is Payments.id
                options += data.map(item =>
                    `<option value="${item.id}">${item.PaymentCode || item.id} — ${item.Amount} ${item.Currency}</option>`
                ).join('');
            }
        } else if (field.options) {
            options = `<option value="">-- Select ${field.label} --</option>` +
                field.options.map(opt => `<option value="${opt}">${opt}</option>`).join('');
        }

        return `<select id="${field.name}" name="${field.name}" ${field.required ? 'required' : ''}>${options}</select>`;
    } else if (field.type === 'textarea') {
        return `<textarea id="${field.name}" name="${field.name}" ${field.required ? 'required' : ''}></textarea>`;
    } else {
        return `<input type="${field.type}" id="${field.name}" name="${field.name}"
                ${field.step ? `step="${field.step}"` : ''}
                ${field.required ? 'required' : ''}>`;
    }
}

function closeModal() {
    document.getElementById('modal').classList.remove('show');
    document.getElementById('recordForm').reset();
    document.querySelector('.modal-actions').style.display = 'flex';
    editingId = null;
}

// ============================================================
//  CRUD Operations
// ============================================================

async function handleFormSubmit(e) {
    e.preventDefault();

    const config = tableConfigs[currentTable];
    const formData = {};

    config.formFields.forEach(field => {
        const input = document.getElementById(field.name);
        if (input) {
            formData[field.name] = input.value || null;
        }
    });

    showLoading(true);

    try {
        const url = editingId ? `/api/${currentTable}/${editingId}` : `/api/${currentTable}`;
        const method = editingId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (result.success) {
            showNotification(editingId ? 'Record updated successfully' : 'Record created successfully', 'success');
            closeModal();
            await loadLookupData();
            await loadData();
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error saving record:', error);
        showNotification('Error saving record', 'error');
    } finally {
        showLoading(false);
    }
}

// ============================================================
//  View Details Modal
// ============================================================

function viewDetails(id) {
    const record = currentData.find(r => r.id === id);
    if (!record) return;

    const config = tableConfigs[currentTable];
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modalTitle');
    const formFields = document.getElementById('formFields');

    modalTitle.textContent = `${config.name} Details — ID: ${id}`;

    const allFields = Object.keys(record)
        .filter(key => key !== 'id')
        .map(key => {
            const displayName = config.displayNames[key] || key;
            let value = formatCell(key, record[key]);
            return `
                <div class="detail-row">
                    <div class="detail-label">${displayName}</div>
                    <div class="detail-value">${value}</div>
                </div>
            `;
        }).join('');

    formFields.innerHTML = `
        <div class="details-container">
            ${allFields}
        </div>
        <div class="details-actions">
            <button type="button" class="btn-edit-full" onclick="editRecordFromDetails(${id})">
                <span>✎</span> Edit
            </button>
            <button type="button" class="btn-delete-full" onclick="deleteRecordFromDetails(${id})">
                <span>✕</span> Delete
            </button>
        </div>
    `;

    document.querySelector('.modal-actions').style.display = 'none';
    modal.classList.add('show');
}

function editRecordFromDetails(id) {
    closeModal();
    setTimeout(() => openModal(id), 300);
}

function deleteRecordFromDetails(id) {
    closeModal();
    setTimeout(() => deleteRecord(id), 300);
}

async function editRecord(id) {
    openModal(id);
}

async function deleteRecord(id) {
    if (!confirm('Are you sure you want to delete this record?')) return;

    showLoading(true);

    try {
        const response = await fetch(`/api/${currentTable}/${id}`, { method: 'DELETE' });
        const result = await response.json();

        if (result.success) {
            showNotification('Record deleted successfully', 'success');
            await loadLookupData();
            await loadData();
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error deleting record:', error);
        showNotification('Error deleting record', 'error');
    } finally {
        showLoading(false);
    }
}

// ============================================================
//  Search
// ============================================================

function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase();
    const config = tableConfigs[currentTable];

    const filtered = currentData.filter(row =>
        config.columns.some(col => {
            const value = row[col];
            return value && value.toString().toLowerCase().includes(searchTerm);
        })
    );

    const originalData = currentData;
    currentData = filtered;
    renderTable();
    currentData = originalData;
}

// ============================================================
//  UI Helpers
// ============================================================

function showLoading(show) {
    const loading = document.getElementById('loading');
    loading.classList.toggle('show', show);
}

function showNotification(message, type = 'info') {
    if (type === 'error') {
        console.error(message);
        alert(message);
    } else {
        console.log(message);
    }
}
