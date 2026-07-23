import sqlite3
import os
import Tablefunctions

# Path resolution
# Tables.py lives in Logic/. MasterDB.db lives in main/.
_LOGIC_DIR    = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_LOGIC_DIR)
DB_PATH       = os.path.join(_PROJECT_ROOT, "main", "MasterDB.db")

conn = sqlite3.connect(DB_PATH)
c =  conn.cursor()


# Tables for the database :
#  1) "Products" which contains the Item ID, name ,description,retail price and office price(wholeSale)
#  2) "Customers" which contains the customer_id ,Name , Phone number, and default Tier (ie wholsale or retail)
#  3) "Orders" which is the overall layout of the bill Invoice Number , , Customer ID( linking to the Customers table), Date, and subtotal , discount, and total, profit , status ( active = ok , canceled = canceled)
#  4) "OrderDetails" which is the details of the order, linking to the Orders table via the Invoice Number, and linking to the Products table via the Item ID, and containing the quantity ordered, and the price sold 



c.execute('''CREATE TABLE IF NOT EXISTS Products (
    Product_ID INTEGER PRIMARY KEY ,
    item_name TEXT,
    description TEXT,
    Retail_Price REAL,
    Wholesale_Price REAL,
    stock_quantity INTEGER,
    Cost REAL DEFAULT 0.0
)''')

c.execute('''CREATE TABLE IF NOT EXISTS customers
              (customer_id INTEGER PRIMARY KEY,
               Name TEXT NOT NULL,
               Phone_Number TEXT ,
               Default_Tier TEXT )''')


c.execute('''CREATE TABLE IF NOT EXISTS orders
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


c.execute('''CREATE TABLE IF NOT EXISTS Expenses (
    Expense_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Category TEXT NOT NULL,          -- 'utility' or 'misc'
    Description TEXT,
    Amount REAL NOT NULL,
    Month TEXT NOT NULL,             -- 'YYYY-MM', the ledger month it's logged to
    Date_Added TEXT NOT NULL         -- actual date the entry was made
)''')

c.execute('''CREATE TABLE IF NOT EXISTS Workers (
    Worker_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Base_Salary REAL NOT NULL DEFAULT 0.0,
    Last_Cashout_Date TEXT NOT NULL   -- salary + adjustments accrue from this date
)''')






conn.commit()
conn.close()
