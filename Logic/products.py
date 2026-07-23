from fastapi import HTTPException
from .db import c




# Pure functions (cursor-based (for concurent API calls ), for FastAPI) 

def get_product_details_pure(cursor, product_id):
    """returns Product_ID, item_name, Retail_Price, Wholesale_Price,stock_quantity,Cost. for a single product, the names of the imported col from the db is lower case to match the api end point call """
    cursor.execute(
        "SELECT Product_ID AS product_id, item_name, Retail_Price AS retail_price, "
        "Wholesale_Price AS wholesale_price, stock_quantity, Cost AS cost "
        "FROM Products WHERE Product_ID = ?",
        (product_id,)
    )
    return cursor.fetchone()


def get_all_products_pure(cursor):
    """returns Product_ID, item_name, Retail_Price, Wholesale_Price,stock_quantity,Cost . for all products, the names of the imported col from the db is lower case to match the api end point call """

    cursor.execute(
        "SELECT Product_ID AS product_id, item_name, Retail_Price AS retail_price, "
        "Wholesale_Price AS wholesale_price, stock_quantity, Cost AS cost "
        "FROM Products"
    )
    return cursor.fetchall()


def insert_new_product_pure(cursor, conn, id, name, retail_price, wholesale_price, *, cost, stock_quantity=None):
    "inserts Product_ID, item_name, Retail_Price, Wholesale_Price, stock_quantity, Cost, in this same order , if no stock has been determined yet 0 should be used "
    cursor.execute(
        """INSERT INTO Products (Product_ID, item_name, Retail_Price, Wholesale_Price, stock_quantity, Cost)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (id, name, retail_price, wholesale_price, stock_quantity, cost)
    )
    return id, name, retail_price, wholesale_price, stock_quantity, cost


def Validate_Products_pure(cursor, product_ids):
    if not product_ids:
        return []
    placeholders = ','.join('?' * len(product_ids))
    query = (
        f"SELECT Product_ID, item_name, Retail_Price, Wholesale_Price, Cost "
        f"FROM Products WHERE Product_ID IN ({placeholders})"
    )
    cursor.execute(query, tuple(product_ids))
    found_products = cursor.fetchall()
    found_ids = [row[0] for row in found_products]
    for p_id in product_ids:
        if p_id not in found_ids:
            raise HTTPException(status_code=404, detail=f"Product ID {p_id} does not exist.")
    return found_products

def update_product_pure(cursor, conn, product_id, **fields):
    """Partial update. Accepts any of: item_name, retail_price, wholesale_price,
    cost, stock_quantity. Only keys actually passed are updated — this lets the
    caller explicitly set stock_quantity=None (untracked) without it being
    confused with 'field not provided'."""
    column_map = {
        "item_name":       "item_name",
        "retail_price":    "Retail_Price",
        "wholesale_price": "Wholesale_Price",
        "cost":            "Cost",
        "stock_quantity":  "stock_quantity",
    }
    set_clauses, values = [], []
    for key, value in fields.items():
        if key in column_map:
            set_clauses.append(f"{column_map[key]} = ?")
            values.append(value)

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No valid fields provided to update.")

    values.append(product_id)
    query = f"UPDATE Products SET {', '.join(set_clauses)} WHERE Product_ID = ?"
    cursor.execute(query, tuple(values))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Product ID {product_id} not found.")

    return get_product_details_pure(cursor, product_id)


def delete_product_pure(cursor, conn, product_id):
    """Refuses to delete a product that appears in any existing order — deleting it
    would orphan OrderDetails rows and break historical invoice lookups."""
    cursor.execute("SELECT COUNT(*) FROM OrderDetails WHERE Item_ID = ?", (product_id,))
    count = cursor.fetchone()[0]
    if count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete product {product_id}: it appears in {count} existing order(s)."
        )
    cursor.execute("DELETE FROM Products WHERE Product_ID = ?", (product_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Product ID {product_id} not found.")
    return product_id


# CLI versions (use module-level cursor) , because these are intended for single-threaded terminal use, not concurrent API calls

def Validate_Products(product_ids):
    if not product_ids:
        return []
    placeholders = ','.join('?' * len(product_ids))
    query = (
        f"SELECT Product_ID, item_name, Retail_Price, Wholesale_Price, Cost "
        f"FROM Products WHERE Product_ID IN ({placeholders})"
    )
    c.execute(query, tuple(product_ids))
    found_products = c.fetchall()
    found_ids = [row[0] for row in found_products]
    for p_id in product_ids:
        if p_id not in found_ids:
            print(f"Error: Product ID {p_id} does not exist in the database.")
            return False
    return found_products


def Get_Product_IDs():
    print(f"\nEnter product IDs one by one. \nType '-1' to exit.")
    product_ids = []
    while True:
        raw = input("> ").strip()
        if raw == '-1':
            break
        if not raw.isdigit():
            print("Invalid input. Please enter a numeric ID.")
            continue
        product_ids.append(int(raw))
    return product_ids if product_ids else False
