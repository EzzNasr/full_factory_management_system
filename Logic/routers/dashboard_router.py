import sqlite3
from typing import Optional

from fastapi import APIRouter, Query, Depends

from Logic import payments as pmt_module
from Logic.dependencies import get_db

router = APIRouter()


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()

    # Top 5 most sold items by qty (Product ID on axis)
    c.execute("""
        SELECT p.Product_ID, SUM(od.Quantity) as total_qty
        FROM OrderDetails od
        JOIN Products p ON od.Item_ID = p.Product_ID
        JOIN Orders o ON o.Invoice_Number = od.Invoice_Number
        WHERE o.Status != 'cancelled'
        GROUP BY p.Product_ID ORDER BY total_qty DESC LIMIT 5
    """)

    top_items = [{"name": str(r[0]), "qty": r[1]} for r in c.fetchall()]

    # Top 3 profitable bills
    c.execute("""
        SELECT o.Invoice_Number, cu.Name, o.Profit FROM Orders o
        JOIN Customers cu ON o.Customer_ID = cu.customer_id
        WHERE o.Status != 'cancelled' ORDER BY o.Profit DESC LIMIT 3
    """)
    top_bills = [{"invoice_number": r[0], "cx_name": r[1], "profit": r[2]} for r in c.fetchall()]

    # Top 3 profitable customers
    c.execute("""
        SELECT cu.Name, SUM(o.Profit) as total_profit FROM Orders o
        JOIN Customers cu ON o.Customer_ID = cu.customer_id
        WHERE o.Status != 'cancelled'
        GROUP BY cu.customer_id ORDER BY total_profit DESC LIMIT 3
    """)
    top_customers = [{"name": r[0], "profit": r[1]} for r in c.fetchall()]

    gross  = pmt_module.calc_gross_profit(c)
    net    = pmt_module.calc_net_profit(c)
    estimated = pmt_module.calc_estimated_profit(c)

    return {
        "top_items":       top_items,
        "top_bills":       top_bills,
        "top_customers":   top_customers,
        # three-tier profit summaries (no breakdown items here — use /profit-breakdown)
        "gross_profit":    gross["total"],
        "net_profit":      net["total"],
        "estimated_profit":estimated["total"],
        "estimated_period_start": estimated["period_start"],
        "estimated_period_end":   estimated["period_end"],
    }

@router.get("/dashboard/profit-breakdown")
async def get_profit_breakdown(
    type: str = Query(..., regex="^(gross|net|estimated)$"),
    period: Optional[str] = Query(None, description="Any date in the target week (YYYY-MM-DD)"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Returns itemized breakdown for one profit model.
    - gross/net: all-time unless `period` supplied (then filters to that Sat-Fri week).
    - estimated: always a single Sat-Fri week (current week if no `period`).
    """
    c = db.cursor()

    period_start = period_end = None
    if period:
        period_start, period_end = pmt_module._week_bounds(period)

    if type == "gross":
        return pmt_module.calc_gross_profit(c, period_start, period_end)
    elif type == "net":
        return pmt_module.calc_net_profit(c, period_start, period_end)
    else:
        return pmt_module.calc_estimated_profit(c, period_start, period_end)
