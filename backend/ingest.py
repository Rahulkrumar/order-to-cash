"""
ingest.py — Load the real SAP O2C JSONL dataset into SQLite.

Key relationships:
  sales_order_headers.soldToParty    → business_partners.customer
  sales_order_items.salesOrder       → sales_order_headers.salesOrder
  sales_order_items.material         → product_descriptions.product
  billing_documents.soldToParty      → business_partners.customer
  billing_documents.accountingDocument → journal_entry_items.accountingDocument
  billing_documents.accountingDocument → payments.accountingDocument
  payments.customer                  → business_partners.customer
  outbound_delivery_headers (linked via customer/timing in graph)
"""

import os, glob, json, sqlite3

DB_PATH = os.environ.get("DB_PATH", "order_to_cash.db")

DATA_DIRS = [
    os.path.join(os.path.dirname(__file__), "data", "sap-o2c-data"),
    os.path.join(os.path.dirname(__file__), "data"),
    "/data/sap-o2c-data",
]


def _find_data_root():
    for d in DATA_DIRS:
        if os.path.isdir(d):
            return d
    return None


def _load_jsonl(folder_path):
    rows = []
    for fpath in sorted(glob.glob(os.path.join(folder_path, "*.jsonl"))):
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


def _safe(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)


def _insert_rows(conn, table, rows):
    if not rows:
        print(f"  {table}: no rows"); return
    cur = conn.execute(f"PRAGMA table_info({table})")
    schema_cols = {r[1] for r in cur.fetchall()}
    cols = [c for c in rows[0].keys() if c in schema_cols]
    if not cols:
        print(f"  {table}: no matching columns"); return
    ph = ",".join("?"*len(cols))
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({ph})"
    data = [tuple(_safe(r.get(c)) for c in cols) for r in rows]
    conn.executemany(sql, data)
    conn.commit()
    print(f"  {table}: {len(data)} rows")


def init_db(conn):
    conn.executescript("""
    PRAGMA journal_mode=WAL;

    CREATE TABLE IF NOT EXISTS business_partners (
        customer TEXT PRIMARY KEY,
        businessPartner TEXT,
        businessPartnerFullName TEXT,
        businessPartnerName TEXT,
        businessPartnerCategory TEXT,
        industry TEXT,
        businessPartnerIsBlocked TEXT,
        creationDate TEXT
    );

    CREATE TABLE IF NOT EXISTS sales_order_headers (
        salesOrder TEXT PRIMARY KEY,
        salesOrderType TEXT,
        salesOrganization TEXT,
        distributionChannel TEXT,
        soldToParty TEXT,
        creationDate TEXT,
        totalNetAmount TEXT,
        transactionCurrency TEXT,
        overallDeliveryStatus TEXT,
        overallOrdReltdBillgStatus TEXT,
        overallSdDocReferenceStatus TEXT,
        requestedDeliveryDate TEXT,
        headerBillingBlockReason TEXT,
        deliveryBlockReason TEXT,
        customerPaymentTerms TEXT,
        totalCreditCheckStatus TEXT,
        pricingDate TEXT
    );

    CREATE TABLE IF NOT EXISTS sales_order_items (
        salesOrder TEXT,
        salesOrderItem TEXT,
        salesOrderItemCategory TEXT,
        material TEXT,
        requestedQuantity TEXT,
        requestedQuantityUnit TEXT,
        transactionCurrency TEXT,
        netAmount TEXT,
        materialGroup TEXT,
        productionPlant TEXT,
        storageLocation TEXT,
        salesDocumentRjcnReason TEXT,
        itemBillingBlockReason TEXT,
        PRIMARY KEY (salesOrder, salesOrderItem)
    );

    CREATE TABLE IF NOT EXISTS product_descriptions (
        product TEXT,
        language TEXT,
        productDescription TEXT,
        PRIMARY KEY (product, language)
    );

    CREATE TABLE IF NOT EXISTS outbound_delivery_headers (
        deliveryDocument TEXT PRIMARY KEY,
        actualGoodsMovementDate TEXT,
        creationDate TEXT,
        deliveryBlockReason TEXT,
        hdrGeneralIncompletionStatus TEXT,
        headerBillingBlockReason TEXT,
        lastChangeDate TEXT,
        overallGoodsMovementStatus TEXT,
        overallPickingStatus TEXT,
        overallProofOfDeliveryStatus TEXT,
        shippingPoint TEXT
    );

    CREATE TABLE IF NOT EXISTS billing_documents (
        billingDocument TEXT PRIMARY KEY,
        billingDocumentType TEXT,
        creationDate TEXT,
        billingDocumentDate TEXT,
        billingDocumentIsCancelled TEXT,
        cancelledBillingDocument TEXT,
        totalNetAmount TEXT,
        transactionCurrency TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        accountingDocument TEXT,
        soldToParty TEXT
    );

    CREATE TABLE IF NOT EXISTS journal_entry_items (
        accountingDocument TEXT,
        accountingDocumentItem TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        glAccount TEXT,
        referenceDocument TEXT,
        costCenter TEXT,
        profitCenter TEXT,
        transactionCurrency TEXT,
        amountInTransactionCurrency TEXT,
        companyCodeCurrency TEXT,
        amountInCompanyCodeCurrency TEXT,
        postingDate TEXT,
        documentDate TEXT,
        accountingDocumentType TEXT,
        assignmentReference TEXT,
        customer TEXT,
        financialAccountType TEXT,
        clearingDate TEXT,
        clearingAccountingDocument TEXT,
        clearingDocFiscalYear TEXT,
        PRIMARY KEY (accountingDocument, accountingDocumentItem)
    );

    CREATE TABLE IF NOT EXISTS payments (
        accountingDocument TEXT,
        accountingDocumentItem TEXT,
        companyCode TEXT,
        fiscalYear TEXT,
        clearingDate TEXT,
        clearingAccountingDocument TEXT,
        clearingDocFiscalYear TEXT,
        amountInTransactionCurrency TEXT,
        transactionCurrency TEXT,
        amountInCompanyCodeCurrency TEXT,
        companyCodeCurrency TEXT,
        customer TEXT,
        invoiceReference TEXT,
        salesDocument TEXT,
        postingDate TEXT,
        documentDate TEXT,
        assignmentReference TEXT,
        glAccount TEXT,
        financialAccountType TEXT,
        profitCenter TEXT,
        costCenter TEXT,
        PRIMARY KEY (accountingDocument, accountingDocumentItem)
    );

    CREATE TABLE IF NOT EXISTS plants (
        plant TEXT PRIMARY KEY,
        plantName TEXT,
        salesOrganization TEXT,
        addressId TEXT,
        plantCategory TEXT,
        distributionChannel TEXT,
        division TEXT,
        language TEXT
    );

    CREATE TABLE IF NOT EXISTS customer_company_assignments (
        customer TEXT,
        companyCode TEXT,
        paymentTerms TEXT,
        reconciliationAccount TEXT,
        paymentMethodsList TEXT,
        PRIMARY KEY (customer, companyCode)
    );

    CREATE TABLE IF NOT EXISTS customer_sales_area_assignments (
        customer TEXT,
        salesOrganization TEXT,
        distributionChannel TEXT,
        division TEXT,
        currency TEXT,
        customerPaymentTerms TEXT,
        deliveryPriority TEXT,
        supplyingPlant TEXT,
        salesDistrict TEXT,
        PRIMARY KEY (customer, salesOrganization, distributionChannel, division)
    );
    """)
    conn.commit()


def ingest_data():
    root = _find_data_root()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if root is None:
        print("No data dir found — seeding demo data.")
        _seed_demo(conn)
        conn.close()
        return

    print(f"Loading from: {root}")
    folder_map = {
        "business_partners":               "business_partners",
        "sales_order_headers":             "sales_order_headers",
        "sales_order_items":               "sales_order_items",
        "product_descriptions":            "product_descriptions",
        "outbound_delivery_headers":       "outbound_delivery_headers",
        "billing_documents":               "billing_document_cancellations",
        "journal_entry_items":             "journal_entry_items_accounts_receivable",
        "payments":                        "payments_accounts_receivable",
        "plants":                          "plants",
        "customer_company_assignments":    "customer_company_assignments",
        "customer_sales_area_assignments": "customer_sales_area_assignments",
    }

    for table, folder_name in folder_map.items():
        folder_path = os.path.join(root, folder_name)
        if not os.path.isdir(folder_path):
            print(f"  {table}: folder not found"); continue
        rows = _load_jsonl(folder_path)
        _insert_rows(conn, table, rows)

    conn.close()
    print("Done.")


def _seed_demo(conn):
    conn.executescript("""
    INSERT OR IGNORE INTO business_partners VALUES
      ('320000083','320000083','Acme Industries Ltd','Acme Industries','2','Manufacturing','false','2024-04-16'),
      ('320000082','320000082','GlobalTech Corp','GlobalTech Corp','2','Technology','false','2024-04-16'),
      ('320000085','320000085','MegaMart Retail','MegaMart Retail','2','Retail','false','2024-04-16');
    INSERT OR IGNORE INTO sales_order_headers VALUES
      ('740506','OR','1710','10','320000083','2025-03-01','9966.10','INR','A','A','','2025-03-15','','','NT30','','2025-03-01'),
      ('740507','OR','1710','10','320000082','2025-03-05','12000.00','INR','C','C','','2025-03-20','','','NT30','','2025-03-05');
    INSERT OR IGNORE INTO sales_order_items VALUES
      ('740506','10','TAN','S8907367001003','48','PC','INR','9966.10','ZFG1001','1920','V2S2','',''),
      ('740507','10','TAN','S8907367001004','10','PC','INR','12000.00','ZFG1001','1920','V2S2','','');
    INSERT OR IGNORE INTO product_descriptions VALUES
      ('S8907367001003','EN','Industrial Valve Type A'),('S8907367001004','EN','Control Panel X200');
    INSERT OR IGNORE INTO billing_documents VALUES
      ('90504274','F2','2025-04-03','2025-04-02','false','','253.39','INR','ABCD','2025','9400000275','320000083'),
      ('90504275','F2','2025-04-04','2025-04-03','false','','897.03','INR','ABCD','2025','9400000220','320000082');
    INSERT OR IGNORE INTO journal_entry_items VALUES
      ('9400000275','1','ABCD','2025','15500020','90504274','','ABC001','INR','-253.39','INR','-253.39','2025-04-03','2025-04-03','RV','','320000083','D','2025-04-10','9400635958','2025'),
      ('9400000220','1','ABCD','2025','15500021','90504275','','ABC001','INR','-897.03','INR','-897.03','2025-04-02','2025-04-02','RV','','320000082','D','2025-04-08','9400635959','2025');
    INSERT OR IGNORE INTO payments VALUES
      ('9400000220','1','ABCD','2025','2025-04-02','9400635977','2025','897.03','INR','897.03','INR','320000083',null,null,'2025-04-02','2025-04-02',null,'15500020','D','ABC001',null),
      ('9400000275','1','ABCD','2025','2025-04-10','9400635958','2025','253.39','INR','253.39','INR','320000082',null,null,'2025-04-10','2025-04-10',null,'15500020','D','ABC001',null);
    """)
    conn.commit()
