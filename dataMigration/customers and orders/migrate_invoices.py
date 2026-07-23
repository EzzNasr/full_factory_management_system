import sqlite3
import pandas as pd
import os
import glob
import datetime

def migrate_all_invoices():
    # 1. recursive File searching for the Excel files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    excel_files = glob.glob('**/*.xlsx', recursive=True)
    
    if not excel_files:
        print(" No Excel (.xlsx) files found in the current directory or its subfolders.")
        return

    print(f" Found {len(excel_files)} files. Starting migration pipeline...\n")

   
    # Goes UP two levels to land exactly in the root "the_invoice_app_V2" folder
    db_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'MasterDB.db'))
    print(f" Connecting to REAL database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except sqlite3.OperationalError as e:
        print(f" Database error. Make sure MasterDB.db is in the parent folder! Error: {e}")
        return

    for file_path in excel_files:
        base_name = os.path.basename(file_path)
        
        # Ignore Microsoft Excel temporary lock files 
        if base_name.startswith('~$'):
            continue
            
        # --- THE FOLDER-BASED NAMING (TWO LEVELS UP) ---
        # file_path is .../Customer_Name/Subfolder/invoice.xlsx
        # os.path.dirname(file_path) gets you .../Customer_Name/Subfolder
        # os.path.dirname(os.path.dirname(file_path)) gets you .../Customer_Name
        # os.path.basename() extracts exactly "Customer_Name"

        grandparent_folder = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
        
        if grandparent_folder:
            customer_name = grandparent_folder.strip()
        else:
            # Fallback: Just in case a file is sitting without a grandparent folder
            customer_name = base_name.split('.xlsx')[0].replace('_invoice_clean', '').replace('_', ' ').strip()
        
        print(f" Processing Invoice for: '{customer_name}' | File: {base_name}")

        # Extract the exact file modification time

        mtime = os.path.getmtime(file_path)
        order_date = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        try:
            xl = pd.ExcelFile(file_path)

            target_sheet = xl.sheet_names[0] # Default fallback
            for name in xl.sheet_names:
                if 'Sheet1' in name or 'sheet1' in name or 'ورقة' in name: #TODO change this condition based on your actual sheet naming conventions
                    target_sheet = name
                    break
            
            print(f"  Reading from sheet: {target_sheet}")
            
            df = xl.parse(target_sheet, skiprows=1)
            df.columns = df.columns.astype(str).str.strip()
            
        except Exception as e:
            print(f"  WARNING \n Could not read file. Skipping. Error: {e}")
            continue

        # DYNAMIC PRICING DETECTION
        retail_col = next((col for col in df.columns if 'جمله' in col or 'جملة' in col), None) #TODO adjust this condition based on your actual sheet naming conventions
        wholesale_col = next((col for col in df.columns if 'مكتب' in col), None)
        
        price_col = None
        detected_tier = 'retail' # Default fallback
        
        # a really dumb way to figure out what tier the bill used but can't think of anything better atm

        if retail_col and wholesale_col:
            qty_col = next((col for col in df.columns if 'عدد' in col), None) #TODO adjust this condition based on your actual sheet naming conventions
            val_col = next((col for col in df.columns if 'قيمة' in col), None)
            
            retail_votes = 0
            wholesale_votes = 0
            
            if qty_col and val_col:
                for _, row in df.head(15).iterrows():
                    try:
                        q = float(row[qty_col])
                        v = float(row[val_col])
                        r_p = float(row[retail_col])
                        w_p = float(row[wholesale_col])
                        
                        if q > 0:
                            if abs((q * r_p) - v) < 1.0: retail_votes += 1
                            if abs((q * w_p) - v) < 1.0: wholesale_votes += 1
                    except (ValueError, TypeError, KeyError):
                        pass
                        
            if wholesale_votes > retail_votes:
                price_col = wholesale_col
                detected_tier = 'wholesale'
            else:
                price_col = retail_col
                detected_tier = 'retail'
                
        elif retail_col:
            price_col = retail_col
            detected_tier = 'retail'
        elif wholesale_col:
            price_col = wholesale_col
            detected_tier = 'wholesale'

        if not price_col:
            print("  WARNING \n Could not find a price column ('سعر الجملة' or 'سعر المكتب'). Skipping.")
            continue

        print(f"  🔍 Detected Pricing Tier: {detected_tier.upper()} (Column: {price_col})") 

        # ORGANIC PARSER & FOOTER FARMING
        items = []
        discount_pct = 0.0

        for index, row in df.iterrows():
            row_str = str(row.values)
            
            # Look for the discount percentage in the footer
            if 'نسبة الخصم' in row_str:
                for val in row.values:
                    try:
                        if pd.notna(val): # Make sure it isn't an empty cell
                            val_float = float(val)
                            if val_float > 0:
                                discount_pct = val_float
                                if discount_pct >= 1: 
                                    discount_pct = discount_pct / 100
                                break # Found the discount, stop looking in this row!
                    except (ValueError, TypeError):
                        pass
                continue

            # Try to process as an Item Row
            try:
                prod_id = int(row['كود الصنف']) #TODO adjust this condition based on your actual sheet naming conventions
                qty = int(row['العدد']) #TODO adjust this condition based on your actual sheet naming conventions
                price = float(row[price_col])
                items.append((prod_id, qty, price))
            except (ValueError, KeyError, TypeError):
                pass

        if not items:
            print("  WARNING \n No valid items found in this file. Skipping database insertion.\n")
            continue

        # Calculate subtotal, discount amount, and final total
        subtotal = sum(qty * price for _, qty, price in items)
        discount_amount = subtotal * discount_pct
        final_total = subtotal - discount_amount

        
        # A. Find or Create Customer (Using cx_ID and Name)
        cursor.execute("SELECT cx_ID FROM Customers WHERE Name = ?", (customer_name,))
        result = cursor.fetchone()
        
        if result:
            cust_id = result[0]
        else:
            cursor.execute("INSERT INTO Customers (Name, Default_Tier) VALUES (?, ?)", (customer_name, detected_tier))
            cust_id = cursor.lastrowid

        # B. Insert Order Header (Using Customer_ID, Subtotal, Discount, Total, Profit)
        cursor.execute('''
            INSERT INTO Orders (Customer_ID, Date, Subtotal, Discount, Total, Profit, Status)
            VALUES (?, ?, ?, ?, ?, 0, 'active')
        ''', (cust_id, order_date, subtotal, discount_amount, final_total))
        order_id = cursor.lastrowid

        # C. Insert the Line Items (Using OrderDetails, Invoice_Number, Item_ID, Quantity, Price_Sold)
        for prod_id, qty, price in items:
            cursor.execute('''
                INSERT INTO OrderDetails (Invoice_Number, Item_ID, Quantity, Price_Sold)
                VALUES (?, ?, ?, ?)
            ''', (order_id, prod_id, qty, price))

        print(f"  Saved Order #{order_id} | Total: {final_total:.2f} EGP | Subtotal: {subtotal:.2f} EGP | (Discount: {discount_pct*100}%)\n")

    conn.commit()
    conn.close()
    print(" MIGRATION COMPLETE! All files grouped by their grandparent folders.")

if __name__ == "__main__":
    migrate_all_invoices()