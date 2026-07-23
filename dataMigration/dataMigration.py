import sqlite3
import pandas as pd
import os
import glob
import datetime

# IMPORTANT:
# Do not use this data-migration script unless your Excel file has the same
# structure as mine, or you can adapt it to match. In particular, review and
# update the column-name's keywords in `find_col()` below to match your file.
# you will find "TODO" to help you easily find where you should edit 
#
# I recommend manually entering old invoices instead, or recording historical
# totals as "Pre-Migration" and new activity as "Post-Migration" in your
# internal books.

def load_price_catalog(catalog_path: str) -> dict:
    try:
        df = pd.read_excel(catalog_path, sheet_name=0)
        df.columns = df.columns.astype(str).str.strip()

        # Locate the required columns by partial name match (handles extra spaces)
        def find_col(df, *keywords):
            for col in df.columns:
                if any(kw.lower() in col.lower() for kw in keywords):
                    return col
            return None


        # TODO Update these keywords if your spreadsheet uses different column names.


        id_col       = find_col(df, 'prod_id') 
        cost_col     = find_col(df, 'cost')
        ws_col       = find_col(df, 'wholesale')
        retail_col   = find_col(df, 'retail')
        name_col     = find_col(df, 'description')

        if not all([id_col, cost_col, ws_col, retail_col]):
            print(" WARNING : \n Price catalog: could not identify required columns. Columns found:", df.columns.tolist())
            return {}

        catalog = {}
        for idc ,row in df.iterrows():
            try:
                prod_id = int(row[id_col])
                catalog[prod_id] = {
                    'cost':      float(row[cost_col]),
                    'wholesale': float(row[ws_col]),
                    'retail':    float(row[retail_col]),
                    'name':      str(row[name_col]).strip() if name_col else f"Product {prod_id}", # if there is no name i will use the prod id as the name 
                }
            except (ValueError, TypeError):
                pass  # skip header artifacts or non-numeric ID rows

        print(f" Price catalog loaded: {len(catalog)} products from '{os.path.basename(catalog_path)}'")
        return catalog

    except Exception as e:
        print(f"\t\t\t ERROR \n Could not load price catalog: {e}")
        return {}


# MAIN MIGRATION

def migrate_all_invoices():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 1. Load price catalog 


    # Adjust this path/filename to wherever your Office Excel file lives.


    catalog_path = os.path.join(script_dir, 'Office_Sanatized.xlsx') # the name of your file , dont't forget the extension (csv,xlsx ,etc)
    if not os.path.exists(catalog_path):
        # Fallback: search for it recursively
        matches = glob.glob('**/*Office*.xlsx', recursive=True) or \
                  glob.glob('**/*office*.xlsx', recursive=True)
        if matches:
            catalog_path = matches[0]
            print(f" CHECK\n Found price catalog at: {catalog_path}")
        else:
            print(" WARNING \n Price catalog file not found. Products will be inserted without catalog prices.")

    price_catalog = load_price_catalog(catalog_path) if os.path.exists(catalog_path) else {}


    #  2. Find invoice files

    #same recursive search to find all invoices in the vicinity of the script 

    excel_files = glob.glob('**/*.xlsx', recursive=True)
    # Exclude the catalog itself from invoice processing
    excel_files = [f for f in excel_files if os.path.abspath(f) != os.path.abspath(catalog_path)]

    if not excel_files:
        print(" WARNING \n No invoice Excel (.xlsx) files found.")
        return

    print(f" \n SUCCESS \n Found {len(excel_files)} invoice file(s). Starting migration pipeline...\n")


    # 3. Connect to DB 

    # the dir structure is as follows 
    # ROOT/
    #   |---- main/
    #   |      └──  main.py
    #   |      └── MasterDB.db
    #   └── logic/
    #      └── *.py  

    db_path = os.path.abspath(os.path.join(script_dir, '..','main', 'MasterDB.db'))

    print(f"  Connecting to database at: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except sqlite3.OperationalError as e:
        print(f"\n ERROR \n Database error: {e}")
        return

    #  4. Process each invoice  ( sanitize , unify name , time stamp it )
    for file_path in excel_files:
        base_name = os.path.basename(file_path)
        if base_name.startswith('~$'): # to ignore the files opened by excel at the moment or in general use by another app 
            continue

        customer_name = (base_name
                         .split('.xlsx')[0]
                         .replace('_invoice_clean', '')
                         .replace('_', ' ')
                         .strip())

        print(f" Processing Invoice for: {customer_name} | File: {base_name}")

        mtime = os.path.getmtime(file_path)
        order_date = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        try:
            xl = pd.ExcelFile(file_path)
            target_sheet = xl.sheet_names[0] # TODO all of my own data was on sheet 1 
            for name in xl.sheet_names:
                if 'Sheet1' in name or 'sheet1' in name or 'ورقة' in name:  # TODO you need to fix this to match your own keyword for the sheet 
                    target_sheet = name
                    break

            print(f"  Reading from sheet: {target_sheet}")
            df = xl.parse(target_sheet, skiprows=1) # TODO skips header 
            df.columns = df.columns.astype(str).str.strip()
        except Exception as e:
            print(f"  WARNING \n Could not read file. Skipping. Error: {e}")
            continue

        # Detect price columns from the invoice (for tier detection)  # NOTE  our invoices have 2 Tiers , modify if yours is more than 2 tiers 


        #TODO keyword matching 

        retail_col    = next((c for c in df.columns if 'جمله' in c or 'جملة' in c), None) 
        wholesale_col = next((c for c in df.columns if 'مكتب' in c), None)

        price_col     = None
        detected_tier = 'retail'

        if retail_col and wholesale_col:
            qty_col = next((c for c in df.columns if 'عدد' in c), None)
            val_col = next((c for c in df.columns if 'قيمة' in c), None)

            # a really dumb way to figure out what tier the bill used but can't think of anything better atm.

            retail_votes = wholesale_votes = 0
            if qty_col and val_col:
                for _, row in df.head(15).iterrows():
                    try:
                        q   = float(row[qty_col])
                        v   = float(row[val_col])
                        r_p = float(row[retail_col])
                        w_p = float(row[wholesale_col])
                        if q > 0:
                            if abs((q * r_p) - v) < 1.0: retail_votes    += 1
                            if abs((q * w_p) - v) < 1.0: wholesale_votes += 1
                    except (ValueError, TypeError, KeyError):
                        pass

            if wholesale_votes > retail_votes:
                price_col     = wholesale_col
                detected_tier = 'wholesale'
            else:
                price_col     = retail_col
                detected_tier = 'retail'
        elif retail_col:
            price_col, detected_tier = retail_col, 'retail'
        elif wholesale_col:
            price_col, detected_tier = wholesale_col, 'wholesale'

        if not price_col:
            print(" WARNING \n Could not find a price column. Skipping.")
            continue

        print(f" SUCCESS \n Detected Pricing Tier: {detected_tier.upper()} (Column: {price_col})")

        #  Parse items 
        items       = []   # (prod_id, qty, price_sold)
        discount_pct = 0.0

        for idk, row in df.iterrows():
            row_str = str(row.values)

            if 'نسبة الخصم' in row_str:
                for val in row.values:
                    try:
                        if pd.notna(val): # find the col 
                            val_float = float(val)
                            if val_float > 0:
                                discount_pct = val_float
                                if discount_pct >= 1: # means it is in pct not decimal
                                    discount_pct /= 100
                                break
                    except (ValueError, TypeError):
                        pass
                continue

            try:
                prod_id = int(row['كود الصنف'])
                qty     = int(row['العدد'])
                price   = float(row[price_col])

                # CATALOG LOOKUP 
                catalog_entry = price_catalog.get(prod_id)

                if catalog_entry:
                    true_cost      = catalog_entry['cost']
                    true_wholesale = catalog_entry['wholesale']
                    true_retail    = catalog_entry['retail']
                    prod_name      = catalog_entry['name']
                else:
                    # Fallback: no catalog entry — use invoice columns if available
                    true_wholesale = float(row[wholesale_col]) if wholesale_col and pd.notna(row.get(wholesale_col)) else price
                    true_retail    = float(row[retail_col])    if retail_col    and pd.notna(row.get(retail_col))    else price
                    true_cost      = true_wholesale * 0.90  # last-resort estimate
                    prod_name      = str(row['اسم الصنف']) if 'اسم الصنف' in df.columns else f"Product {prod_id}"
                    print(f" prod_id {prod_id} not in catalog — using invoice fallback.")



                items.append((prod_id, qty, price, true_cost))

            except (ValueError, KeyError, TypeError):
                pass

        if not items:
            print(" WARNING \n No valid items found. Skipping.\n")
            continue

        # Financials
        subtotal        = sum(qty * price for _, qty, price, _ in items)
        discount_amount = subtotal * discount_pct
        final_total     = subtotal - discount_amount

        # True cost uses actual per-item cost from catalog 
        total_cost = sum(qty * true_cost for _, qty, _, true_cost in items)

        # Apply the same discount logic to cost (cost of goods for what was actually sold)
        cost_of_goods_sold = total_cost * (1 - discount_pct)
        profit = final_total - cost_of_goods_sold

        # DB Inserts 
        cursor.execute("SELECT customer_id FROM Customers WHERE Name = ?", (customer_name,))
        result = cursor.fetchone()
        if result:
            cust_id = result[0]
        else:
            cursor.execute("INSERT INTO Customers (Name, Default_Tier) VALUES (?, ?)",
                           (customer_name, detected_tier))
            cust_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO Orders (Customer_ID, Date, Subtotal, Discount, Total, Profit, Status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        ''', (cust_id, order_date, subtotal, discount_amount, final_total, profit))
        order_id = cursor.lastrowid

        for prod_id, qty, price, _ in items:
            cursor.execute('''
                INSERT INTO OrderDetails (Invoice_Number, Item_ID, Quantity, Price_Sold)
                VALUES (?, ?, ?, ?)
            ''', (order_id, prod_id, qty, price))

        print(f"  ✅ Saved Order #{order_id} | Total: {final_total:.2f} EGP | "
              f"Subtotal: {subtotal:.2f} EGP | Profit: {profit:.2f} EGP "
              f"(Discount: {discount_pct * 100:.0f}%)\n")

    conn.commit()
    conn.close()
    print("🎉 MIGRATION COMPLETE! All files processed.")


if __name__ == "__main__":
    migrate_all_invoices()