import sqlite3
import os


# Path resolution

# Tables.py lives in Logic/. MasterDB.db lives in main/.

_LOGIC_DIR    = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_LOGIC_DIR)
DB_PATH       = os.path.join(_PROJECT_ROOT, "main", "MasterDB.db")


# Tables for the database :
#  1) "Products" which contains the Item ID, name ,description,retail price and office price(wholeSale)
#  2) "Customers" which contains the customer_id ,Name , Phone number, and default Tier (ie wholsale or retail)
#  3) "Orders" which is the overall layout of the bill Invoice Number , , Customer ID( linking to the Customers table), Date, and subtotal , discount, and total, profit , status ( active = ok , canceled = canceled)
#  4) "OrderDetails" which is the details of the order, linking to the Orders table via the Invoice Number, and linking to the Products table via the Item ID, and containing the quantity ordered, and the price sold
#  5) "Payments" which logs every payment/refund/credit-applied transaction against an invoice
#  6) "Expenses" which logs utility/misc business expenses per ledger month
#  7) "Workers" which holds each worker's base salary and salary-accrual clock
#  8) "WorkerLedger" which logs bonuses/deductions/adjustments per worker, each marked paid/unpaid
#  9) "WorkerCashouts" which logs each payout event to a worker


def ensure_schema(conn: sqlite3.Connection):
    """
    Creates every table this app depends on if it doesn't already exist,
    and adds any columns that were introduced after the original CREATE
    TABLE (via guarded ALTER TABLE, since SQLite has no
    "ADD COLUMN IF NOT EXISTS"). Safe to call multiple times.

    This is meant to be called ONCE at application startup.
    """
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS Products (
        Product_ID INTEGER PRIMARY KEY ,
        item_name TEXT,
        description TEXT,
        Retail_Price REAL,
        Wholesale_Price REAL,
        stock_quantity INTEGER,
        Cost REAL DEFAULT 0.0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS Customers
                  (customer_id INTEGER PRIMARY KEY,
                   Name TEXT NOT NULL,
                   Phone_Number TEXT ,
                   Default_Tier TEXT )''')

    c.execute('''CREATE TABLE IF NOT EXISTS Orders
                  (Invoice_Number INTEGER PRIMARY KEY AUTOINCREMENT,
                   Customer_ID INTEGER NOT NULL,
                   Date TEXT NOT NULL,
                   Subtotal REAL NOT NULL,
                   Discount REAL NOT NULL,
                   Total REAL NOT NULL,
                   Profit REAL NOT NULL,
                   Status TEXT NOT NULL,
                   FOREIGN KEY (Customer_ID) REFERENCES Customers(customer_id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS OrderDetails
                  (Invoice_Number INTEGER NOT NULL,
                   Item_ID INTEGER NOT NULL,
                   Quantity INTEGER NOT NULL,
                   Price_Sold REAL NOT NULL,
                   FOREIGN KEY (Invoice_Number) REFERENCES Orders(Invoice_Number),
                   FOREIGN KEY (Item_ID) REFERENCES Products(Product_ID))''')

    # payment transactions table
    c.execute("""CREATE TABLE IF NOT EXISTS Payments (
            Payment_ID     INTEGER PRIMARY KEY AUTOINCREMENT,
            Invoice_Number INTEGER NOT NULL,
            Amount         REAL NOT NULL,
            Type           TEXT NOT NULL CHECK(Type IN ('payment','refund','credit_applied')),
            Date           TEXT NOT NULL,
            Note           TEXT
        )""")
    # Both indexes support the lookups payments.py does constantly:
    # balance_due (per invoice) and any date-ranged reporting/ledger views.
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON Payments(Invoice_Number)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_date    ON Payments(Date)")
    except Exception:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS Expenses (
        Expense_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Category TEXT NOT NULL,          -- 'utility' or 'misc'
        Description TEXT,
        Amount REAL NOT NULL,
        Month TEXT NOT NULL,             -- 'YYYY-MM', the ledger month it's logged to
        Date_Added TEXT NOT NULL         -- actual date the entry was made
    )''')

    # worker ledger and cashouts tables
    c.execute('''CREATE TABLE IF NOT EXISTS Workers (
        Worker_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Base_Salary REAL NOT NULL DEFAULT 0.0,
        Last_Cashout_Date TEXT NOT NULL   -- salary + adjustments accrue from this date
    )''')
    # Active lets a worker be hidden from active-only lists without erasing
    # their payroll history & added after the original CREATE TABLE, so it
    # has to come in via ALTER TABLE for any DB that predates this column ( Backwards-compatible schema migration ).
    try:
        c.execute("ALTER TABLE Workers ADD COLUMN Active INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS WorkerLedger (
            Ledger_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Worker_ID INTEGER NOT NULL,
            Date TEXT NOT NULL,
            Type TEXT NOT NULL,
            Amount REAL NOT NULL,
            Note TEXT,
            FOREIGN KEY (Worker_ID) REFERENCES Workers(Worker_ID)
        )""")
    try:
        c.execute("ALTER TABLE WorkerLedger ADD COLUMN Paid INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS WorkerCashouts (
            Cashout_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Worker_ID INTEGER NOT NULL,
            Date TEXT NOT NULL,
            Amount_Paid REAL NOT NULL,
            Note TEXT,
            FOREIGN KEY (Worker_ID) REFERENCES Workers(Worker_ID)
        )""")

    conn.commit()


if __name__ == "__main__":

    # this makes it still be run standalone/manually 
    # to set up or patch an existing DB without starting the whole app.
    _conn = sqlite3.connect(DB_PATH)
    ensure_schema(_conn)
    _conn.close()