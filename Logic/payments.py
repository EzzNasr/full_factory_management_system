"""
Logic/payments.py

# Payments table + pure functions for all payment-related endpoints.

Schema is created by Tables.ensure_schema(conn), called once at app
startup look at Tables.py for further details. This module assumes Payments, Orders, Customers,
Expenses, Workers, and WorkerCashouts already exist by the time any
function here runs.

balance_due formula (status-aware , accounts for Process3_cancel preserving Total):
    effective_total = 0.0 if Orders.Status == 'cancelled' else Orders.Total
    balance_due     = effective_total - SUM(Payments.Amount WHERE Invoice_Number = ?)

Net Profit uses only real cash movements:
    SUM(Payments.Amount WHERE Type != 'credit_applied') - SUM(Expenses) - SUM(WorkerCashouts)
    credit_applied is a bookkeeping transfer between invoices, no cash changes hands.
"""
import datetime
import sqlite3


def _today() -> str:
    return datetime.date.today().isoformat()


def _week_bounds(date_str: str | None = None) -> tuple[str, str]:
    """Returns (saturday_ISO, friday_ISO) for the week containing date_str (or today).
    Pay period is Saturday → Friday."""
    d = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    days_since_sat = (d.weekday() - 5) % 7   # Monday=0 … Saturday=5
    sat = d - datetime.timedelta(days=days_since_sat)
    fri = sat + datetime.timedelta(days=6)
    return sat.isoformat(), fri.isoformat()


#  Per-invoice helpers 

def get_payments_for_invoice(c: sqlite3.Cursor, invoice_number: int) -> list:
    """Returns [(payment_id, amount, type, date, note), ...]."""
    c.execute(
        """SELECT Payment_ID, Amount, Type, Date, Note
           FROM Payments WHERE Invoice_Number = ? ORDER BY Date DESC, Payment_ID DESC""",
        (invoice_number,)
    )
    return c.fetchall()


def compute_balance_due(c: sqlite3.Cursor, invoice_number: int,
                         status: str, total: float) -> float:
    effective_total = 0.0 if status == "cancelled" else float(total)
    c.execute("SELECT COALESCE(SUM(Amount), 0) FROM Payments WHERE Invoice_Number = ?",
              (invoice_number,))
    paid = c.fetchone()[0]
    return round(effective_total - float(paid), 2)


def add_payment_pure(c: sqlite3.Cursor, invoice_number: int, amount: float,
                      type_: str, date: str | None, note: str | None) -> int:
    c.execute(
        "INSERT INTO Payments (Invoice_Number, Amount, Type, Date, Note) VALUES (?, ?, ?, ?, ?)",
        (invoice_number, amount, type_, date or _today(), note)
    )
    return c.lastrowid


def apply_credit_pure(c: sqlite3.Cursor, source_invoice: int,
                       target_invoice: int, amount: float):
    """Two-row atomic credit transfer. No real cash ( invisible to Net Profit)."""
    today = _today()
    c.execute(
        "INSERT INTO Payments (Invoice_Number, Amount, Type, Date, Note) VALUES (?, ?, 'credit_applied', ?, ?)",
        (source_invoice, -abs(amount), today, f"Credit applied → Invoice #{target_invoice}")
    )
    c.execute(
        "INSERT INTO Payments (Invoice_Number, Amount, Type, Date, Note) VALUES (?, ?, 'credit_applied', ?, ?)",
        (target_invoice, abs(amount), today, f"Credit from Invoice #{source_invoice}")
    )


#  Customer-level helpers 

def get_customer_balances(c: sqlite3.Cursor, customer_id: int) -> list[dict]:
    """All invoices for a customer with their real-time balance_due."""
    c.execute(
        """SELECT Invoice_Number, Date, Total, Status
           FROM Orders WHERE Customer_ID = ? ORDER BY Invoice_Number ASC""",
        (customer_id,)
    )
    rows = c.fetchall()
    result = []
    for inv_num, date, total, status in rows:
        balance = compute_balance_due(c, inv_num, status, total)
        result.append({
            "invoice_number": inv_num,
            "date": date,
            "total": total,
            "status": status,
            "balance_due": balance,
        })
    return result


def get_credit_invoices(c: sqlite3.Cursor, customer_id: int) -> list[dict]:
    """Invoices for this customer currently sitting at a negative balance
    (store credit , usually from an overpayment or a return after payment)."""
    return [b for b in get_customer_balances(c, customer_id) if b["balance_due"] < 0]


def sweep_available_credit(c: sqlite3.Cursor, customer_id: int, target_invoice: int) -> float:
    """Applies this customer's available credit (oldest credit first) into
    target_invoice, up to whatever it currently owes. Returns the total
    amount actually applied (0.0 if nothing was owed or nothing was
    available). This is what makes a new bill automatically reflect any
    store credit the customer already has, instead of requiring a manual
    credit-apply for every new invoice."""
    c.execute("SELECT Total, Status FROM Orders WHERE Invoice_Number = ?", (target_invoice,))
    row = c.fetchone()
    if not row:
        raise ValueError(f"Invoice {target_invoice} not found")
    target_total, target_status = row
    remaining_owed = compute_balance_due(c, target_invoice, target_status, target_total)
    if remaining_owed <= 0:
        return 0.0

    total_applied = 0.0
    for credit in get_credit_invoices(c, customer_id):
        if remaining_owed <= 0:
            break
        if credit["invoice_number"] == target_invoice:
            continue
        available = -credit["balance_due"]  # stored as negative, flip to positive
        apply_amount = round(min(available, remaining_owed), 2)
        if apply_amount > 0:
            apply_credit_pure(c, credit["invoice_number"], target_invoice, apply_amount)
            remaining_owed = round(remaining_owed - apply_amount, 2)
            total_applied = round(total_applied + apply_amount, 2)
    return total_applied


def bulk_allocate_payments(c: sqlite3.Cursor,
                            allocations: list[dict], date: str | None = None):
    """Write one payment row per allocation. All Type='payment'."""
    today = date or _today()
    for alloc in allocations:
        c.execute(
            "INSERT INTO Payments (Invoice_Number, Amount, Type, Date, Note) VALUES (?, ?, 'payment', ?, ?)",
            (alloc["invoice_number"], alloc["amount"], today, alloc.get("note"))
        )


#  Dashboard profit calculations

def calc_gross_profit(c: sqlite3.Cursor, period_start: str | None = None,
                       period_end: str | None = None) -> dict:
    if period_start and period_end:
        c.execute(
            """SELECT COALESCE(SUM(o.Profit), 0),
                      json_group_array(json_object(
                          'invoice_number', o.Invoice_Number,
                          'cx_name', cu.Name,
                          'date', o.Date,
                          'profit', o.Profit
                      ))
               FROM Orders o JOIN Customers cu ON cu.customer_id = o.Customer_ID
               WHERE o.Status != 'cancelled' AND o.Date BETWEEN ? AND ?
               ORDER BY o.Date DESC""",
            (period_start, period_end)
        )
    else:
        c.execute(
            """SELECT COALESCE(SUM(o.Profit), 0),
                      json_group_array(json_object(
                          'invoice_number', o.Invoice_Number,
                          'cx_name', cu.Name,
                          'date', o.Date,
                          'profit', o.Profit
                      ))
               FROM Orders o JOIN Customers cu ON cu.customer_id = o.Customer_ID
               WHERE o.Status != 'cancelled'"""
        )
    row = c.fetchone()
    total = row[0] or 0
    import json
    items = json.loads(row[1]) if row[1] and row[1] != "[null]" else []
    return {"total": round(total, 2), "items": items}


def calc_net_profit(c: sqlite3.Cursor, period_start: str | None = None,
                     period_end: str | None = None) -> dict:
    import json

    date_filter = "AND p.Date BETWEEN ? AND ?" if period_start else ""
    params_p = (period_start, period_end) if period_start else ()
    c.execute(
        f"""SELECT COALESCE(SUM(p.Amount), 0),
                  json_group_array(json_object(
                      'invoice_number', p.Invoice_Number,
                      'amount', p.Amount,
                      'type', p.Type,
                      'date', p.Date,
                      'note', p.Note
                  ))
           FROM Payments p WHERE p.Type != 'credit_applied' {date_filter}""",
        params_p
    )
    prow = c.fetchone()
    cash_in = prow[0] or 0
    payment_items = json.loads(prow[1]) if prow[1] and prow[1] != "[null]" else []

    date_filter_e = "WHERE e.Date_Added BETWEEN ? AND ?" if period_start else ""
    params_e = (period_start, period_end) if period_start else ()
    c.execute(
        f"""SELECT COALESCE(SUM(e.Amount), 0),
                  json_group_array(json_object(
                      'expense_id', e.Expense_ID,
                      'category', e.Category,
                      'description', e.Description,
                      'amount', e.Amount,
                      'date', e.Date_Added
                  ))
           FROM Expenses e {date_filter_e}""",
        params_e
    )
    erow = c.fetchone()
    expenses_total = erow[0] or 0
    expense_items = json.loads(erow[1]) if erow[1] and erow[1] != "[null]" else []

    date_filter_c = "AND wc.Date BETWEEN ? AND ?" if period_start else ""
    params_c = (period_start, period_end) if period_start else ()
    c.execute(
        f"""SELECT COALESCE(SUM(wc.Amount_Paid), 0),
                  json_group_array(json_object(
                      'worker_name', w.Name,
                      'date', wc.Date,
                      'amount_paid', wc.Amount_Paid,
                      'note', wc.Note
                  ))
           FROM WorkerCashouts wc JOIN Workers w ON w.Worker_ID = wc.Worker_ID
           {date_filter_c}""",
        params_c
    )
    crow = c.fetchone()
    cashouts_total = crow[0] or 0
    cashout_items = json.loads(crow[1]) if crow[1] and crow[1] != "[null]" else []

    total = round(cash_in - expenses_total - cashouts_total, 2)
    return {
        "total": total,
        "cash_in": round(cash_in, 2),
        "expenses_total": round(expenses_total, 2),
        "cashouts_total": round(cashouts_total, 2),
        "payment_items": payment_items,
        "expense_items": expense_items,
        "cashout_items": cashout_items,
    }


def calc_estimated_profit(c: sqlite3.Cursor, period_start: str | None = None,
                           period_end: str | None = None) -> dict:
    """Uses the current week if no period provided. Base_Salary is weekly."""
    import json
    sat, fri = _week_bounds(period_start) if period_start else _week_bounds()
    if not period_end:
        period_end = fri
    period_start = sat

    c.execute(
        """SELECT COALESCE(SUM(o.Total), 0),
                  json_group_array(json_object(
                      'invoice_number', o.Invoice_Number,
                      'cx_name', cu.Name,
                      'date', o.Date,
                      'total', o.Total
                  ))
           FROM Orders o JOIN Customers cu ON cu.customer_id = o.Customer_ID
           WHERE o.Status != 'cancelled' AND o.Date BETWEEN ? AND ?""",
        (period_start, period_end)
    )
    orow = c.fetchone()
    orders_total = orow[0] or 0
    order_items = json.loads(orow[1]) if orow[1] and orow[1] != "[null]" else []

    c.execute(
        """SELECT COALESCE(SUM(Amount), 0),
                  json_group_array(json_object(
                      'category', Category, 'description', Description,
                      'amount', Amount, 'date', Date_Added
                  ))
           FROM Expenses WHERE Date_Added BETWEEN ? AND ?""",
        (period_start, period_end)
    )
    erow = c.fetchone()
    expenses_total = erow[0] or 0
    expense_items = json.loads(erow[1]) if erow[1] and erow[1] != "[null]" else []

    # Base_Salary is the weekly figure , used directly, no proration
    c.execute("SELECT Worker_ID, Name, Base_Salary FROM Workers WHERE Active = 1")
    worker_rows = c.fetchall()
    workers_total = sum(r[2] for r in worker_rows)
    worker_items = [{"worker_id": r[0], "name": r[1], "weekly_salary": r[2]} for r in worker_rows]

    total = round(orders_total - expenses_total - workers_total, 2)
    return {
        "total": total,
        "period_start": period_start,
        "period_end": period_end,
        "orders_total": round(orders_total, 2),
        "expenses_total": round(expenses_total, 2),
        "workers_total": round(workers_total, 2),
        "order_items": order_items,
        "expense_items": expense_items,
        "worker_items": worker_items,
    }