import sqlite3
import datetime
import re

from fastapi import HTTPException

from .db         import DB_PATH, get_stock_config
from .customers  import (handle_existing_customer, handle_new_customer,
                          Current_Tier, get_customer_list_pure,
                          get_customer_by_id_pure, find_customer_by_name_pure,
                          create_new_customer_pure)
from .products   import Get_Product_IDs, Validate_Products
from .cart       import Quantity_System
from .financials import (Calculate_Subtotal, Apply_Discount, Apply_Taxes,
                          Calculate_Profit, Package_Invoice_Data,fmt)
from .invoice_output import invoice_Generation, Render_Invoice_HTML, Save_And_Open_Invoice


# Phase 1: Customer identification + tier

def Phase1_Process1():
    while True:
        choice = input("Choose 1 for existing customer \nChoose 2 for new customer\n: ").strip()
        if choice == '1':
            cx_id, cx_name, cx_tier = handle_existing_customer()
        elif choice == '2':
            cx_id, cx_name, cx_tier = handle_new_customer()
        else:
            print(f"'{choice}' is an invalid choice. Let's try that again.\n")
            continue
        final_id, final_name, final_tier = Current_Tier(cx_id, cx_name, cx_tier)
        return (final_id, final_name, final_tier)


# Phase 2: Product entry + validation

def Phase2_Process1():
    customer_id, Name, Tier = Phase1_Process1()
    while True:
        raw_user_input_ids = Get_Product_IDs()
        if not raw_user_input_ids:
            print("No valid items entered. Let's try again.")
            continue
        valid_products = Validate_Products(raw_user_input_ids)
        if not valid_products:
            print("Validation failed. Invalid IDs were entered. Please re-enter your list.")
        else:
            print(f"\nSuccess! Ready to process: {valid_products}")
            return customer_id, Name, Tier, valid_products


# Phase 3: Quantity entry + cart building

def Phase3_Process1():
    customer_id, Name, tier, valid_products = Phase2_Process1()
    final_cart = Quantity_System(valid_products, tier)
    print(f"\nPhase 3 Done. Going into discount and Totals.")
    return customer_id, Name, tier, final_cart


# Phase 4: Financials + packaging

def Phase4_Process1():
    customer_id, cx_name, tier, final_cart = Phase3_Process1()

    subtotal                                 = Calculate_Subtotal(final_cart)
    discounted_total, discount_amount, discount_pct = Apply_Discount(subtotal)
    grand_total, tax_amount, tax_rate        = Apply_Taxes(discounted_total)
    profit, total_order_cost                 = Calculate_Profit(final_cart, subtotal, discount_amount)

    invoice_packet = Package_Invoice_Data(
        cx_name, tier, final_cart, subtotal, discount_amount,
        discount_pct, tax_amount, grand_total, profit
    )

    invoice_date = datetime.datetime.now().strftime("%Y-%m-%d")

    return {
        "customer_id":    customer_id,
        "cx_name":        cx_name,
        "cx_tier":        tier,
        "final_cart":     final_cart,
        "invoice_packet": invoice_packet,
        "financials": {
            "subtotal":        subtotal,
            "discount_amount": discount_amount,
            "discount_pct":    discount_pct,
            "tax_amount":      tax_amount,
            "grand_total":     grand_total,
            "profit":          profit,
        },
        "invoice_date": invoice_date,
    }


# Process1 (assembles all 4 phases, read-only)

def Process1():
    return Phase4_Process1()


# Shared core: writes customer/order/order-detail rows for one invoice.
# Used by both Process2 (CLI) and Process2_pure (FastAPI) so the actual
# insert/stock logic only exists in one place. Does NOT commit, rollback,
# or catch exceptions itself - that's the caller's job, since the CLI and
# FastAPI wrappers need different transaction and error-reporting behavior.

def _write_order_core(c_w, pipeline_data):
    """Returns (invoice_number, customer_id, new_customer_created, stock_warnings).
    stock_warnings is a list of (product_id, item_name, new_stock_quantity) tuples."""
    customer_id = pipeline_data["customer_id"]
    cx_name     = pipeline_data["cx_name"]
    cx_tier     = pipeline_data["cx_tier"]
    final_cart  = pipeline_data["final_cart"]
    fin         = pipeline_data["financials"]
    inv_date    = pipeline_data["invoice_date"]

    new_customer_created = customer_id == 0
    if new_customer_created:
        c_w.execute(
            "INSERT INTO Customers (Name, Phone_Number, Default_Tier) VALUES (?, ?, ?)",
            (cx_name, None, cx_tier)
        )
        customer_id = c_w.lastrowid

    c_w.execute(
        """INSERT INTO Orders
           (Customer_ID, Date, Subtotal, Discount, Total, Profit, Status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (customer_id, inv_date, fin["subtotal"], fin["discount_amount"],
         fin["grand_total"], fin["profit"], "active")
    )
    invoice_number = c_w.lastrowid

    track_stock = get_stock_config()
    stock_warnings = []

    for item in final_cart:
        p_id, qty, line_cost, line_price, p_name = item
        unit_price_sold = line_price / qty
        c_w.execute(
            """INSERT INTO OrderDetails
               (Invoice_Number, Item_ID, Quantity, Price_Sold)
               VALUES (?, ?, ?, ?)""",
            (invoice_number, p_id, qty, unit_price_sold)
        )
        if track_stock:
            # COALESCE handles never-tracked (NULL) products by treating them as 0 first.
            # Negative stock is allowed on purpose, see STOCK_TRACKING.md.
            c_w.execute(
                "UPDATE Products SET stock_quantity = COALESCE(stock_quantity, 0) - ? WHERE Product_ID = ?",
                (qty, p_id)
            )
            c_w.execute("SELECT stock_quantity FROM Products WHERE Product_ID = ?", (p_id,))
            new_stock = c_w.fetchone()[0]
            if new_stock < 0:
                stock_warnings.append((p_id, p_name, new_stock))

    return invoice_number, customer_id, new_customer_created, stock_warnings


# Process2 (CLI version, own write connection)

def Process2(pipeline_data):
    conn_w = sqlite3.connect(DB_PATH)
    conn_w.execute("PRAGMA foreign_keys = OFF")
    c_w = conn_w.cursor()
    try:
        invoice_number, customer_id, new_customer_created, stock_warnings = \
            _write_order_core(c_w, pipeline_data)

        if new_customer_created:
            print(f"New customer '{pipeline_data['cx_name']}' added, ID {customer_id}.")
        print(f"Order header written. Invoice Number: {invoice_number}")

        conn_w.commit()
        print(f"{len(pipeline_data['final_cart'])} line item(s) written. Transaction committed.")

        if stock_warnings:
            print("STOCK WARNING, the following items are now oversold:")
            for p_id, p_name, new_stock in stock_warnings:
                print(f"   - {p_name} (ID {p_id}): stock is now {new_stock}")

        return invoice_number

    except Exception as e:
        conn_w.rollback()
        print(f"DB write failed, rolled back.\n   Error: {e}")
        raise
    finally:
        conn_w.close()


# Process2_pure (FastAPI version, uses injected connection)

def Process2_pure(db_conn, pipeline_data):
    c_w = db_conn.cursor()
    try:
        invoice_number, customer_id, new_customer_created, stock_warnings_raw = \
            _write_order_core(c_w, pipeline_data)

        stock_warnings = [
            {"product_id": p_id, "item_name": p_name, "stock_quantity": new_stock}
            for p_id, p_name, new_stock in stock_warnings_raw
        ]

        db_conn.commit()
        return invoice_number, stock_warnings

    except Exception as e:
        db_conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}")


# Process3 (return / cancel pipeline)

def Process3_logic(invoice_number_str):
    """Pure lookup, raises ValueError on any problem."""
    try:
        inv_num = int(str(invoice_number_str).strip())
    except (ValueError, AttributeError):
        raise ValueError("Invoice number must be a whole number.")

    conn_r = sqlite3.connect(DB_PATH)
    cr     = conn_r.cursor()
    try:
        cr.execute(
            """SELECT o.Invoice_Number, c.Name, o.Date, o.Total, o.Profit, o.Status
               FROM Orders o
               JOIN Customers c ON c.customer_id = o.Customer_ID
               WHERE o.Invoice_Number = ?""",
            (inv_num,)
        )
        row = cr.fetchone()
        if not row:
            raise ValueError(f"Invoice #{inv_num} not found in the database.")

        inv_num_db, cx_name, inv_date, total, profit, status = row

        if status == "cancelled":
            raise ValueError(f"Invoice #{inv_num} is already cancelled.")

        cr.execute(
            """SELECT p.item_name, od.Quantity, od.Price_Sold
               FROM OrderDetails od
               JOIN Products p ON p.Product_ID = od.Item_ID
               WHERE od.Invoice_Number = ?""",
            (inv_num,)
        )
        line_items = cr.fetchall()

        return {
            "invoice_number": inv_num_db,
            "cx_name":        cx_name,
            "inv_date":       inv_date,
            "total":          total,
            "profit":         profit,
            "line_items":     line_items,
        }
    finally:
        conn_r.close()


def Process3_cancel(inv_num, restore_stock=None):
    """Pure write, marks 'cancelled'. Restores stock if track_stock is on in config,
    unless the caller explicitly overrides via restore_stock=True/False."""
    if restore_stock is None:
        restore_stock = get_stock_config()

    conn_w = sqlite3.connect(DB_PATH)
    conn_w.execute("PRAGMA foreign_keys = OFF")
    cw = conn_w.cursor()
    try:
        cw.execute("UPDATE Orders SET Status = 'cancelled' WHERE Invoice_Number = ?", (inv_num,))
        cw.execute("UPDATE Orders SET Profit = 0 WHERE Invoice_Number = ?", (inv_num,))
        if restore_stock:
            cw.execute(
                "SELECT Item_ID, Quantity FROM OrderDetails WHERE Invoice_Number = ?", (inv_num,)
            )
            for item_id, qty in cw.fetchall():
                # Same COALESCE fix as the sale-side decrement, untracked (NULL) products
                # are treated as starting at 0 the first time stock is touched.
                cw.execute(
                    "UPDATE Products SET stock_quantity = COALESCE(stock_quantity, 0) + ? WHERE Product_ID = ?",
                    (qty, item_id)
                )
        conn_w.commit()
        return inv_num
    except Exception as e:
        conn_w.rollback()
        raise RuntimeError(f"DB write failed during cancellation, rolled back.\n   Error: {e}")
    finally:
        conn_w.close()



def Process3():
    """CLI wrapper for the full return pipeline."""
    while True:
        raw = input("\nEnter the Invoice Number to return/cancel: ").strip()
        try:
            summary = Process3_logic(raw)
        except ValueError as e:
            print(f"{e}\n")
            retry = input("Try another number? (y/n): ").strip().lower()
            if retry != "y":
                print("Returning to main menu.")
                return
            continue

        inv_num  = summary["invoice_number"]
        cx_name  = summary["cx_name"]
        inv_date = summary["inv_date"]
        total    = summary["total"]
        items    = summary["line_items"]

        print(f"""
┌─────────────────────────────────────────────────────┐
│              INVOICE RETURN SUMMARY                 │
├─────────────────────────────────────────────────────┤
│  Invoice # : {inv_num:<38}                          │
│  Customer  : {cx_name:<38}                          │
│  Date      : {inv_date:<38}                         │
│  Total Paid: EGP{total:<37.2f}                      │
├─────────────────────────────────────────────────────┤""")
        for name, qty, price in items:
            line = f"{name} x{qty} @ EGP{price:.2f}"
            print(f"│  {line:<51}│")
        print("└─────────────────────────────────────────────────┘")

        confirm = input("\nConfirm return? (y/n): ").strip().lower()
        if confirm != "y":
            print("Return aborted. No changes made.")
            return

        try:
            Process3_cancel(inv_num)
        except RuntimeError as e:
            print(f"{e}")
            return

        print(f"Invoice #{inv_num} marked as cancelled. Stock quantities restored.")

        # Render a RETURNED-stamped invoice
        returned_packet = {
            "header": {"customer_name": cx_name, "tier": "-"},
            "table_data": [
                ["", qty, f"EGP{price:.2f}", f"EGP{price * qty:.2f}", name]
                for name, qty, price in items
            ],
            "financials": {
                "subtotal":        f"EGP{total:.2f}",
                "discount_pct":    0,
                "discount_amount": "EGP0.00",
                "after_discount":  f"EGP{total:.2f}",
                "discount":        "EGP0.00",
                "tax":             "EGP0.00",
                "grand_total":     f"EGP{total:.2f}",
            },
            "system_metrics": {"internal_profit": "EGP0.00"},
        }

        date_dd_mm_yy = datetime.datetime.now().strftime("%d-%m-%y")
        cx_slug       = cx_name.replace(" ", "_")
        returned_slug = f"{cx_slug}--invoice#{inv_num}--{date_dd_mm_yy}--RETURNED"

        html = Render_Invoice_HTML(returned_packet, f"#{inv_num} - RETURNED", inv_date, mode="client")
        returned_banner = """
  <div style="background:#c0392b;color:#fff;text-align:center;padding:14px 0;
              font-size:1.1rem;font-weight:700;letter-spacing:0.15em;
              margin-bottom:16px;border-radius:4px;">
    RETURNED / CANCELLED - THIS INVOICE HAS BEEN REVERSED
  </div>"""
        html = html.replace('<div class="wrapper">', f'<div class="wrapper">{returned_banner}', 1)
        Save_And_Open_Invoice(html, returned_slug, cx_name=cx_name)
        print(f"Returned bill generated and opened.")
        return


# bill_type, main entry point

def bill_type():
    while True:
        print("""
┌──────────────────────────────────────────────────────────────┐
│                    THE INVOICE APP  V2                       │
├──────────────────────────────────────────────────────────────┤
│  1)  Mock Bill     - preview only, zero DB changes           │
│  2)  Actual Bill   - saves to DB, issues a real Invoice #    │
│  3)  Returned Bill - reverse / cancel an existing invoice    │
└──────────────────────────────────────────────────────────────┘""")
        choice = input("\nEnter bill type (1 / 2 / 3): ").strip()

        if choice == "1":
            print("\n[ MOCK BILL PIPELINE, no DB changes will be made ]\n")
            pipeline_data = Process1()
            cx_slug       = pipeline_data["cx_name"].replace(" ", "_")
            date_dd_mm_yy = datetime.datetime.now().strftime("%d-%m-%y")
            mock_slug     = f"{cx_slug}--invoice#MOCK--{date_dd_mm_yy}"
            invoice_Generation(
                pipeline_data["invoice_packet"], mock_slug,
                pipeline_data["invoice_date"], cx_name=pipeline_data["cx_name"],
            )
            print(f"\nMock bill generated. No DB changes made.")
            break

        elif choice == "2":
            print("\n[ ACTUAL BILL PIPELINE ]\n")
            pipeline_data       = Process1()
            real_invoice_number = Process2(pipeline_data)
            cx_slug             = pipeline_data["cx_name"].replace(" ", "_")
            date_dd_mm_yy       = datetime.datetime.now().strftime("%d-%m-%y")
            invoice_slug        = f"{cx_slug}--invoice#{real_invoice_number}--{date_dd_mm_yy}"
            invoice_Generation(
                pipeline_data["invoice_packet"], invoice_slug,
                pipeline_data["invoice_date"], cx_name=pipeline_data["cx_name"],
            )
            print(f"\nInvoice #{real_invoice_number} committed to DB.")
            break

        elif choice == "3":
            print("\n[ RETURNED BILL PIPELINE ]\n")
            Process3()
            break

        else:
            print("\nInvalid choice, please enter 1, 2, or 3.\n")