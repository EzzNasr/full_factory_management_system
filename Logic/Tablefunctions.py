import sqlite3
import os
from tabulate import tabulate

#NOTE just internal functions for viewing and clearing tables, not intended for external use.

# directories 
_LOGIC_DIR    = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_LOGIC_DIR)
DB_PATH       = os.path.join(_PROJECT_ROOT, "main", "MasterDB.db")


def PrintALL(table):
    conn = sqlite3.connect(DB_PATH)
    c= conn.cursor()
    c.execute(f"SELECT * FROM {table}")

    print(f"ID\tDescription\t\t\tPrice(office)\tPrice(retail)")  

    for row in c.fetchall():
        print(f"{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}")


def  Print_noDescription(table):
    conn = sqlite3.connect(DB_PATH)
    c= conn.cursor()
    c.execute(f"SELECT * FROM {table}")
    print(f"ID\tPrice(office)\tPrice(retail)")
    for row in c.fetchall():
        print(f"{row[0]}\t{row[2]}\t\t{row[3]}")

def  ViewDB():
    conn = sqlite3.connect(DB_PATH)
    c= conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print(c.fetchall())

def ViewTable(table):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # sanatize the table name to be able to make each table presentation 
    clean_table = str(table).strip().lower()

    try:
        # We pass the original 'table' string to SQLite since it already works
        c.execute(f"SELECT * FROM {table}")
    except sqlite3.OperationalError:
        print(f" Table '{table}' does not exist in the database at {DB_PATH}")
        conn.close()
        return

    # Now we compare against our sanitized, lowercase string
    if clean_table == "products":
        headers = ["Prod ID", "Item Name", "Description", "Retail Price", "Wholesale", "Stock", "Cost"]
        
        # Process and format the rows
        table_data = []
        for row in c.fetchall():
            table_data.append([
                row[0], 
                row[1], 
                row[2], 
                f"{float(row[3]):.2f}",  # Retail Price
                f"{float(row[4]):.2f}",  # Wholesale
                row[5] if row[5] is not None else "—",  # Stock (untracked)
                f"{float(row[6]):.2f}"   # Cost
            ])
        
        print(tabulate(table_data, headers=headers, tablefmt="grid", stralign="right"))
        print("\n")

    elif clean_table == "customers":
        print("-" * 70)
        print(f"{'ID':<5} | {'Name':<20} | {'Phone Number':<15} | {'Default Tier':<15}")
        print("-" * 70)
        for row in c.fetchall():
            print(f"{str(row[0]):<5} | {str(row[1]):<20} | {str(row[2]):<15} | {str(row[3]):<15}")
        print("-" * 70 + "\n")
        
    elif clean_table == "orders":
        print("-" * 115)
        print(f"{'Inv #':<6} | {'Cust ID':<8} | {'Date':<20} | {'Subtotal':<10} | {'Discount':<10} | {'Total':<10} | {'Profit':<10} | {'Status':<8}")
        print("-" * 115)
        for row in c.fetchall():

        # Applying the .2f format to make all financial columns look presentable 
            print(f"{row[0]:<6} | {row[1]:<8} | {str(row[2]):<20} | {float(row[3]):<10.2f} | {float(row[4]):<10.2f} | {float(row[5]):<10.2f} | {float(row[6]):<10.2f} | {str(row[7]):<8}")
        print("-" * 115 + "\n")
        
    elif clean_table == "orderdetails":
        print("-" * 50)
        print(f"{'Inv #':<8} | {'Item ID':<8} | {'Quantity':<10} | {'Price Sold':<12}")
        print("-" * 50)
        for row in c.fetchall():
            print(f"{str(row[0]):<8} | {str(row[1]):<8} | {str(row[2]):<10} | {str(row[3]):<12}")
        print("-" * 50 + "\n")
        
    else:
        print(f"table is seen , but no headers designed for: '{table}'")

    conn.close()

def ClearTable(table):
    #table clear but still exists 
    conn = sqlite3.connect(DB_PATH)
    c= conn.cursor()
    c.execute(f"DELETE FROM {table}")
    conn.commit()
    print(f" Cleared all records from {table}.")   


def DropTable(table):
    # fully evaporate table 
    conn = sqlite3.connect(DB_PATH)
    c= conn.cursor()
    c.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    print(f" Dropped table {table}.")

