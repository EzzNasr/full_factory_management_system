import sqlite3

from fastapi import APIRouter, HTTPException, Depends

from Logic import payments as pmt_module
from Logic.dependencies import get_db
from Logic.schemas import PaymentCreate, CreditApply, BulkPaymentRequest

router = APIRouter()


#  Per-invoice payments 

@router.get("/orders/{invoice_number}/payments")
async def get_invoice_payments(invoice_number: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT Invoice_Number, Total, Status FROM Orders WHERE Invoice_Number = ?",
              (invoice_number,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    _, total, status = row

    payments = pmt_module.get_payments_for_invoice(c, invoice_number)
    balance_due = pmt_module.compute_balance_due(c, invoice_number, status, total)

    return {
        "invoice_number": invoice_number,
        "total": total,
        "status": status,
        "balance_due": balance_due,
        "payments": [
            {"payment_id": p[0], "amount": p[1], "type": p[2], "date": p[3], "note": p[4]}
            for p in payments
        ],
    }

@router.post("/customers/{customer_id}/sweep-credit/{invoice_number}")
async def sweep_credit(customer_id: int, invoice_number: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT customer_id FROM Customers WHERE customer_id = ?", (customer_id,))
    if not c.fetchone():
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        applied = pmt_module.sweep_available_credit(c, customer_id, invoice_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    db.commit()
    return {"applied": applied}


@router.post("/orders/{invoice_number}/payments")
async def log_invoice_payment(
    invoice_number: int,
    payment: PaymentCreate,
    db: sqlite3.Connection = Depends(get_db),
):
    c = db.cursor()
    c.execute("SELECT Invoice_Number, Total, Status FROM Orders WHERE Invoice_Number = ?",
              (invoice_number,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    _, total, status = row
    if status == "cancelled" and payment.type == "payment":
        raise HTTPException(status_code=400,
                            detail="Cannot log a payment against a cancelled order. Use refund or credit_applied.")

    pid = pmt_module.add_payment_pure(c, invoice_number, payment.amount,
                                       payment.type, payment.date, payment.note)
    db.commit()
    balance_due = pmt_module.compute_balance_due(c, invoice_number, status, total)
    return {"payment_id": pid, "balance_due": balance_due}


@router.post("/orders/credit-apply")
async def apply_store_credit(req: CreditApply, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    for inv_num in (req.source_invoice, req.target_invoice):
        c.execute("SELECT Invoice_Number FROM Orders WHERE Invoice_Number = ?", (inv_num,))
        if not c.fetchone():
            raise HTTPException(status_code=404, detail=f"Invoice #{inv_num} not found")
    pmt_module.apply_credit_pure(c, req.source_invoice, req.target_invoice, req.amount)
    db.commit()
    return {"message": f"Credit of {req.amount} applied from #{req.source_invoice} → #{req.target_invoice}"}


#  Customer-level balance + bulk payment 

@router.get("/customers/{customer_id}/balances")
async def get_customer_balances(customer_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    c.execute("SELECT customer_id FROM Customers WHERE customer_id = ?", (customer_id,))
    if not c.fetchone():
        raise HTTPException(status_code=404, detail="Customer not found")
    balances = pmt_module.get_customer_balances(c, customer_id)
    return balances


@router.post("/customers/{customer_id}/payments")
async def bulk_allocate(
    customer_id: int,
    req: BulkPaymentRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    c = db.cursor()
    # Validate all invoices belong to this customer
    for alloc in req.allocations:
        c.execute("SELECT Customer_ID FROM Orders WHERE Invoice_Number = ?", (alloc.invoice_number,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Invoice #{alloc.invoice_number} not found")
        if row[0] != customer_id:
            raise HTTPException(status_code=400,
                                detail=f"Invoice #{alloc.invoice_number} does not belong to customer {customer_id}")
    pmt_module.bulk_allocate_payments(
        c,
        [{"invoice_number": a.invoice_number, "amount": a.amount, "note": a.note}
         for a in req.allocations],
        req.date,
    )
    db.commit()
    return {"message": f"{len(req.allocations)} payment(s) recorded."}
