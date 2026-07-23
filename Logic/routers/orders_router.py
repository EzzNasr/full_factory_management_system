import datetime
import sqlite3

from fastapi import APIRouter, HTTPException, Depends

from Logic import functions
from Logic import payments as pmt_module
from Logic.dependencies import get_db
from Logic.schemas import InvoiceRequest, ReturnRequest

router = APIRouter()


#  Order endpoints 

@router.get("/orders")
async def get_all_orders(db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("""
        SELECT o.Invoice_Number, o.Date, cu.Name
        FROM Orders o
        JOIN Customers cu ON o.Customer_ID = cu.customer_id
        ORDER BY o.Invoice_Number DESC
    """)
    return [{"invoice_number": r[0], "date": r[1], "cx_name": r[2]} for r in c.fetchall()]

@router.get("/orders/{invoice_number}")
async def get_order_detail(invoice_number: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("""
        SELECT o.Invoice_Number, o.Date, o.Subtotal, o.Discount, o.Total,
               o.Profit, o.Status, cu.Name, cu.Default_Tier
        FROM Orders o
        JOIN Customers cu ON o.Customer_ID = cu.customer_id
        WHERE o.Invoice_Number = ?
    """, (invoice_number,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    c.execute("""
        SELECT od.Item_ID, p.item_name, od.Quantity, od.Price_Sold
        FROM OrderDetails od
        JOIN Products p ON od.Item_ID = p.Product_ID
        WHERE od.Invoice_Number = ?
    """, (invoice_number,))
    items = [{"product_id": r[0], "name": r[1], "qty": r[2],
              "unit_price": r[3], "line_total": r[2] * r[3]} for r in c.fetchall()]
    return {"invoice_number": row[0], "date": row[1], "subtotal": row[2],
            "discount": row[3], "total": row[4], "profit": row[5],
            "status": row[6], "cx_name": row[7], "tier": row[8], "items": items}

@router.post("/return-invoice")
async def return_invoice(req: ReturnRequest, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT Invoice_Number, Status FROM Orders WHERE Invoice_Number = ?", (req.invoice_number,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Invoice #{req.invoice_number} not found.")
    if row[1] == "cancelled":
        raise HTTPException(status_code=400, detail=f"Invoice #{req.invoice_number} is already cancelled.")
    try:
        functions.Process3_cancel(req.invoice_number)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    track_stock = functions.get_stock_config()
    msg = (f"Invoice #{req.invoice_number} cancelled. Stock restored."
           if track_stock else f"Invoice #{req.invoice_number} cancelled.")
    return {"message": msg}

@router.post("/generate-invoice")
async def generate_invoice(invoice_req: InvoiceRequest, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()

    # 1. Customer
    final_tier = invoice_req.tier_choice
    if invoice_req.customer_id:
        row = functions.get_customer_by_id_pure(c, invoice_req.customer_id)
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        final_id, final_name = row[0], row[1]
    elif invoice_req.customer_name:
        row = functions.find_customer_by_name_pure(c, invoice_req.customer_name)
        if row:
            final_id, final_name = row[0], row[1]
        else:
            final_id, final_name = 0, invoice_req.customer_name
    else:
        raise HTTPException(status_code=400, detail="customer_id or customer_name required.")

    # 2. Validate products
    product_ids = [item.product_id for item in invoice_req.order_items]
    valid_products = functions.Validate_Products_pure(c, product_ids)
    if not valid_products:
        raise HTTPException(status_code=400, detail="One or more product IDs are invalid.")

    # 3. Build cart
    quantities = {item.product_id: item.quantity for item in invoice_req.order_items}
    final_cart = []
    for prod in valid_products:
        p_id, p_name, p_retail, p_wholesale, p_cost = prod
        qty = quantities.get(p_id, 1)
        active_price = p_wholesale if final_tier == "wholesale" else p_retail
        final_cart.append((p_id, qty, p_cost * qty, active_price * qty, p_name))

    # 4. Financials
    subtotal_preview = sum(item[3] for item in final_cart)
    discount_pct     = functions.parse_discount_input(invoice_req.discount_input, subtotal_preview)
    apply_tax, tax_rate = functions.get_tax_config()
    financials = functions.Calculate_Financials_pure(final_cart, discount_pct, invoice_req.apply_tax, tax_rate)
    invoice_date   = datetime.datetime.now().strftime("%d-%m-%Y")
    invoice_packet = functions.Package_Invoice_Data(
        final_name, final_tier, final_cart,
        financials["subtotal"], financials["discount_amount"], discount_pct,
        financials["tax_amount"], financials["grand_total"], financials["profit"]
    )
    pipeline_data = {
        "customer_id": final_id, "cx_name": final_name, "cx_tier": final_tier,
        "final_cart": final_cart, "financials": financials, "invoice_date": invoice_date,
    }

    # 5. DB write for actual bills
    invoice_number  = "MOCK"
    stock_warnings  = []
    final_customer_id = final_id
    if invoice_req.bill_type == "actual":
        real_invoice_number, stock_warnings = functions.Process2_pure(db, pipeline_data)
        invoice_number = str(real_invoice_number)
        final_customer_id = final_id if final_id != 0 else pipeline_data["customer_id"]
        # if a brand-new customer was created inside Process2_pure, re-read
        # the actual customer_id it assigned (customer_id==0 meant "new" going in)
        c.execute("SELECT Customer_ID FROM Orders WHERE Invoice_Number = ?", (real_invoice_number,))
        final_customer_id = c.fetchone()[0]

        if invoice_req.amount_paid_now and invoice_req.amount_paid_now > 0:
            pmt_module.add_payment_pure(
                c, real_invoice_number, invoice_req.amount_paid_now,
                "payment", None, "Paid at invoice creation",
            )
            db.commit()

    amount_paid = invoice_req.amount_paid_now or 0.0
    if amount_paid > 0:
        balance_due = financials["grand_total"] - amount_paid
        invoice_packet["financials"]["amount_paid"] = f"EGP{amount_paid:.2f}"
        invoice_packet["financials"]["balance_due"]  = f"EGP{balance_due:.2f}"
    # else: leave both keys absent entirely — template correctly skips the rows

    # 6. Generate files
    cx_slug      = final_name.replace(" ", "_")
    date_slug    = datetime.datetime.now().strftime("%d-%m-%y")
    invoice_slug = f"{cx_slug}--invoice#{invoice_number}--{date_slug}"

    html_content  = functions.Render_Invoice_HTML(invoice_packet, invoice_number, invoice_date, mode="management")
    html_path, mgmt_pdf_path = functions.Save_And_Open_Invoice(html_content, invoice_slug, cx_name=final_name, output_dir=None)
    client_pdf_path = functions.Save_Client_PDF(
        invoice_packet, invoice_slug, invoice_number, invoice_date,
        cx_name=final_name, business_name="NAVY LLC", output_dir=None
    )

    return {
        "message":            f"Invoice {invoice_number} generated successfully.",
        "invoice_number":     invoice_number,
        "customer_id":        final_customer_id,   # NEW — needed for credit sweep
        "html_path":          html_path,
        "management_pdf_path": mgmt_pdf_path,
        "client_pdf_path":    client_pdf_path,
        "stock_warnings":     stock_warnings,
    }
