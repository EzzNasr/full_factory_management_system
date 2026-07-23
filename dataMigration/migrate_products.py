"""
Data Migration Script
Source : Office_Sanatized.xlsx  (Sheet: "Table 1")
Target : MasterDB.db            (Table: Products)

Column Mapping:
    prod_ID          -> Product_ID      (INTEGER PRIMARY KEY)
    Description      -> item_name       (TEXT)  — used as the display name
    Description      -> description     (TEXT)  — same field, full Arabic text
    Retail price     -> Retail_Price    (REAL)
    WholeSale price  -> Wholesale_Price (REAL)
    quantity         -> stock_quantity  (INTEGER, NaN -> 0)
    Cost             -> Cost            (REAL)

Note:
    - `price/prod` column is all zeros and has no matching DB column; it is skipped.
    - quantity is fully NULL in the source file and defaults to 0.
    - All 147 rows carry unique prod_ID values (1-147), so no PK conflicts expected.
    - The script is idempotent: it uses INSERT OR REPLACE so re-running it is safe.
"""

import os
import sqlite3
import pandas as pd


#  Paths 
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path    = os.path.abspath(os.path.join(script_dir, '..', 'main', 'MasterDB.db'))
xlsx_path  = os.path.abspath(os.path.join(script_dir, 'Office_Sanatized.xlsx'))


# Load Excel 
print(f"Reading: {xlsx_path}")
df = pd.read_excel(xlsx_path, sheet_name='Table 1')

# Strip whitespace from column names (some may have trailing spaces)
df.columns = df.columns.str.strip()

print(f"  Rows loaded : {len(df)}")
print(f"  Columns     : {list(df.columns)}")


#Transform 

# Rename to DB column names
df = df.rename(columns={
    'prod_ID'        : 'Product_ID',
    'Description'    : 'description',
    'Retail price'   : 'Retail_Price',
    'WholeSale price': 'Wholesale_Price',
    'quantity'       : 'stock_quantity',
    'Cost'           : 'Cost',
})

# item_name = description (no separate name column in the source) #TODO this is special to my own source, yours may not have this, so adjust accordingly 
df['item_name'] = df['description']

# quantity is fully NaN in source — leave as NULL (untracked), not 0 (zero stock)
df['stock_quantity'] = df['stock_quantity'].astype('Int64')  # nullable pandas int, preserves NaN as pd.NA

# Ensure numeric types are clean
df['Retail_Price']    = pd.to_numeric(df['Retail_Price'],    errors='coerce').fillna(0.0)
df['Wholesale_Price'] = pd.to_numeric(df['Wholesale_Price'], errors='coerce').fillna(0.0)
df['Cost']            = pd.to_numeric(df['Cost'],            errors='coerce').fillna(0.0)
df['Product_ID']      = df['Product_ID'].astype(int)

# Keep only the columns the Products table expects
migration_df = df[[
    'Product_ID',
    'item_name',
    'description',
    'Retail_Price',
    'Wholesale_Price',
    'stock_quantity',
    'Cost',
]]

print(f"\nSample rows after transformation:")
print(migration_df.head(3).to_string(index=False))


# Connect & Ensure Table Exists 
print(f"\nConnecting to: {db_path}")
con = sqlite3.connect(db_path)
c = con.cursor()
    
c.execute('''CREATE TABLE IF NOT EXISTS Products (
    Product_ID      INTEGER PRIMARY KEY,
    item_name       TEXT,
    description     TEXT,
    Retail_Price    REAL,
    Wholesale_Price REAL,
    stock_quantity  INTEGER,
    Cost            REAL DEFAULT 0.0
)''')
con.commit()


#  Insert 

# Convert pd.NA to standard Python None so SQLite can bind it as NULL
rows = list(migration_df.replace({pd.NA: None}).itertuples(index=False, name=None))
c.executemany(
    '''INSERT OR REPLACE INTO Products
       (Product_ID, item_name, description, Retail_Price, Wholesale_Price, stock_quantity, Cost)
       VALUES (?, ?, ?, ?, ?, ?, ?)''',
    rows
)
con.commit()

inserted = c.rowcount  # rows affected by last executemany
print(f"\nMigration complete.")
print(f"  Rows written : {len(rows)}")


#  Verify
c.execute("SELECT COUNT(*) FROM Products")
total = c.fetchone()[0]
print(f"  Total rows in Products table: {total}")

c.execute("SELECT * FROM Products LIMIT 5")
print("\nFirst 5 rows in DB:")
cols = [d[0] for d in c.description]
print("  " + " | ".join(cols))
print("  " + "-" * 90)
for row in c.fetchall():
    print("  " + " | ".join(str(v) for v in row))

con.close()
print("\nDone.")
