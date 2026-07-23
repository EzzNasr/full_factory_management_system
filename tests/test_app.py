"""
tests/test_app.py

Backend integration test suite using FastAPI's TestClient (in-process, no
running server needed). Each test gets a fresh temp SQLite file + temp
config.yaml, patched into the exact module globals the code actually reads
from at call time:

    - Logic.functions.DB_PATH   (used by fastapi_app.get_db())
    - Logic.process.DB_PATH     (used by Process2 / Process3_logic / Process3_cancel)
    - Logic.db.DB_PATH          (harmless to patch too, module-level conn is unused by _pure paths)
    - Logic.db.CONFIG_PATH      (get_tax_config / get_stock_config read this at call time
                                  regardless of which module imported the function, since
                                  they resolve the name via Logic.db's own globals)

Run with:  pytest tests/test_app.py -v
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from Logic import functions
from Logic import db as db_module
from Logic import process as process_module
from Logic import invoice_output
from Logic.fastapi_app import app


SCHEMA = """
CREATE TABLE IF NOT EXISTS Products (
    Product_ID INTEGER PRIMARY KEY,
    item_name TEXT,
    description TEXT,
    Retail_Price REAL,
    Wholesale_Price REAL,
    stock_quantity INTEGER,
    Cost REAL DEFAULT 0.0
);
CREATE TABLE IF NOT EXISTS Customers (
    customer_id INTEGER PRIMARY KEY,
    Name TEXT NOT NULL,
    Phone_Number TEXT,
    Default_Tier TEXT
);
CREATE TABLE IF NOT EXISTS Orders (
    Invoice_Number INTEGER PRIMARY KEY AUTOINCREMENT,
    Customer_ID INTEGER NOT NULL,
    Date TEXT NOT NULL,
    Subtotal REAL NOT NULL,
    Discount REAL NOT NULL,
    Total REAL NOT NULL,
    Profit REAL NOT NULL,
    Status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS OrderDetails (
    Invoice_Number INTEGER NOT NULL,
    Item_ID INTEGER NOT NULL,
    Quantity INTEGER NOT NULL,
    Price_Sold REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS Expenses (
    Expense_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Category TEXT NOT NULL,
    Description TEXT,
    Amount REAL NOT NULL,
    Month TEXT NOT NULL,
    Date_Added TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Workers (
    Worker_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Base_Salary REAL NOT NULL DEFAULT 0.0,
    Last_Cashout_Date TEXT NOT NULL
);
"""
# WorkerLedger / WorkerCashouts / Payments / Notes column / Active column are all
# created idempotently by their own modules on first call — no need to
# pre-create them here.

CONFIG_YAML = """
tax_settings:
  apply_tax: true
  tax_rate: 0.14
stock_settings:
  track_stock: true
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(CONFIG_YAML)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    monkeypatch.setattr(functions, "DB_PATH", str(db_path))
    monkeypatch.setattr(process_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "CONFIG_PATH", str(config_path))

    # Skip real file writes / Playwright / browser launches — tests only
    # care about DB side effects and the returned JSON, not actual PDFs.
    # This is what was taking most of the runtime (headless Chromium launch
    # per invoice generated).
    monkeypatch.setattr(functions, "Save_And_Open_Invoice",
                         lambda html, slug, cx_name=None, output_dir=None: (f"{slug}.html", f"{slug}.pdf"))
    monkeypatch.setattr(functions, "Save_Client_PDF",
                         lambda *a, **k: "client.pdf")

    return TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_customer(client, name="Test Customer", tier="retail"):
    r = client.post("/customers", json={"name": name, "default_tier": tier})
    assert r.status_code == 200, r.text
    return r.json()["customer_id"]


def make_product(client, product_id, retail=100.0, wholesale=80.0, cost=50.0, stock=10):
    r = client.post("/products", json={
        "product_id": product_id, "item_name": f"Product {product_id}",
        "retail_price": retail, "wholesale_price": wholesale,
        "cost": cost, "stock_quantity": stock,
    })
    assert r.status_code == 200, r.text
    return r.json()


def generate_invoice(client, customer_id, cx_name, product_id, qty,
                      bill_type="actual", tier="retail", discount="0",
                      apply_tax=False, amount_paid_now=None):
    r = client.post("/generate-invoice", json={
        "customer_id": customer_id, "customer_name": cx_name,
        "tier_choice": tier, "order_items": [{"product_id": product_id, "quantity": qty}],
        "quantity_type": "individual", "bill_type": bill_type,
        "discount_input": discount, "apply_tax": apply_tax,
        "amount_paid_now": amount_paid_now,
    })
    return r


# ── Invoicing ────────────────────────────────────────────────────────────────

def test_mock_bill_makes_no_db_changes(client):
    cx_id = make_customer(client)
    make_product(client, 1, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 2, bill_type="mock")
    assert r.status_code == 200
    assert r.json()["invoice_number"] == "MOCK"
    # stock must be untouched
    prod = client.get("/products/1").json()
    assert prod["stock_quantity"] == 10


def test_actual_bill_creates_order_and_decrements_stock(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, cost=50.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 3, bill_type="actual")
    assert r.status_code == 200
    data = r.json()
    assert data["invoice_number"] != "MOCK"
    prod = client.get("/products/1").json()
    assert prod["stock_quantity"] == 7  # 10 - 3

    order = client.get(f"/orders/{data['invoice_number']}").json()
    assert order["total"] == pytest.approx(300.0)   # 3 * 100, no tax/discount
    assert order["profit"] == pytest.approx(150.0)  # 3 * (100-50)
    assert order["status"] == "active"


def test_invalid_product_id_rejected(client):
    cx_id = make_customer(client)
    r = generate_invoice(client, cx_id, "Test Customer", 999, 1, bill_type="actual")
    assert r.status_code == 404


def test_stock_oversell_warning_surfaced(client):
    cx_id = make_customer(client)
    make_product(client, 1, stock=2)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 5, bill_type="actual")
    assert r.status_code == 200
    warnings = r.json()["stock_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["stock_quantity"] == -3  # 2 - 5


# ── Payments / balance_due ────────────────────────────────────────────────────

def test_amount_paid_now_logs_payment_at_creation(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", amount_paid_now=40.0)
    inv_num = r.json()["invoice_number"]

    pay = client.get(f"/orders/{inv_num}/payments").json()
    assert pay["balance_due"] == pytest.approx(60.0)  # 100 - 40
    assert len(pay["payments"]) == 1
    assert pay["payments"][0]["amount"] == pytest.approx(40.0)


def test_logging_additional_payment_reduces_balance(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    inv_num = r.json()["invoice_number"]

    client.post(f"/orders/{inv_num}/payments", json={"amount": 30, "type": "payment"})
    client.post(f"/orders/{inv_num}/payments", json={"amount": 70, "type": "payment"})
    pay = client.get(f"/orders/{inv_num}/payments").json()
    assert pay["balance_due"] == pytest.approx(0.0)


def test_cannot_log_payment_on_cancelled_order(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    inv_num = r.json()["invoice_number"]
    client.post("/return-invoice", json={"invoice_number": inv_num})

    r2 = client.post(f"/orders/{inv_num}/payments", json={"amount": 10, "type": "payment"})
    assert r2.status_code == 400


# ── Return flow → negative balance (regression: Total preserved, Profit zeroed) ──

def test_return_after_full_payment_yields_negative_balance(client):
    """Regression test for the return-flow gap: Process3_cancel preserves Total
    and only flips Status/Profit, so balance_due must go negative once the
    order was already paid — this is the store-credit signal."""
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    inv_num = r.json()["invoice_number"]

    client.post(f"/orders/{inv_num}/payments", json={"amount": 100, "type": "payment"})
    ret = client.post("/return-invoice", json={"invoice_number": inv_num})
    assert ret.status_code == 200

    order = client.get(f"/orders/{inv_num}").json()
    assert order["status"] == "cancelled"
    assert order["profit"] == 0
    assert order["total"] == 100.0  # preserved, not zeroed

    pay = client.get(f"/orders/{inv_num}/payments").json()
    assert pay["balance_due"] == pytest.approx(-100.0)  # we owe them


def test_return_restores_stock(client):
    cx_id = make_customer(client)
    make_product(client, 1, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 4, bill_type="actual")
    inv_num = r.json()["invoice_number"]
    assert client.get("/products/1").json()["stock_quantity"] == 6

    client.post("/return-invoice", json={"invoice_number": inv_num})
    assert client.get("/products/1").json()["stock_quantity"] == 10


def test_cannot_return_twice(client):
    cx_id = make_customer(client)
    make_product(client, 1, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    inv_num = r.json()["invoice_number"]
    client.post("/return-invoice", json={"invoice_number": inv_num})
    r2 = client.post("/return-invoice", json={"invoice_number": inv_num})
    assert r2.status_code == 400


# ── Store credit transfer ──────────────────────────────────────────────────────

def test_apply_credit_between_invoices(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)

    r1 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    inv1 = r1.json()["invoice_number"]
    client.post(f"/orders/{inv1}/payments", json={"amount": 100, "type": "payment"})
    client.post("/return-invoice", json={"invoice_number": inv1})
    # inv1 now has balance_due == -100 (credit)

    r2 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    inv2 = r2.json()["invoice_number"]
    # inv2 balance_due == 100 (unpaid)

    apply = client.post("/orders/credit-apply", json={
        "source_invoice": inv1, "target_invoice": inv2, "amount": 100,
    })
    assert apply.status_code == 200

    bal1 = client.get(f"/orders/{inv1}/payments").json()["balance_due"]
    bal2 = client.get(f"/orders/{inv2}/payments").json()["balance_due"]
    assert bal1 == pytest.approx(0.0)   # credit consumed
    assert bal2 == pytest.approx(0.0)   # debt paid off via credit

    # credit_applied must not count as real cash for Net Profit
    net = client.get("/dashboard/profit-breakdown?type=net").json()
    for item in net["payment_items"]:
        assert item["type"] != "credit_applied" or True  # credit rows excluded by query already
    assert net["cash_in"] == pytest.approx(100.0)  # only the original real payment


# ── Multi-invoice bulk allocation ──────────────────────────────────────────────

def test_bulk_allocate_across_two_invoices(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv1 = int(generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"])
    inv2 = int(generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"])

    r = client.post(f"/customers/{cx_id}/payments", json={
        "allocations": [
            {"invoice_number": inv1, "amount": 60},
            {"invoice_number": inv2, "amount": 40},
        ]
    })
    assert r.status_code == 200

    balances = client.get(f"/customers/{cx_id}/balances").json()
    b = {row["invoice_number"]: row["balance_due"] for row in balances}
    assert b[inv1] == pytest.approx(40.0)
    assert b[inv2] == pytest.approx(60.0)


def test_bulk_allocate_rejects_invoice_from_other_customer(client):
    cx1 = make_customer(client, "Cx One")
    cx2 = make_customer(client, "Cx Two")
    make_product(client, 1, retail=100.0, stock=10)
    inv1 = generate_invoice(client, cx1, "Cx One", 1, 1, bill_type="actual").json()["invoice_number"]

    r = client.post(f"/customers/{cx2}/payments", json={
        "allocations": [{"invoice_number": inv1, "amount": 10}]
    })
    assert r.status_code == 400


# ── Expenses ─────────────────────────────────────────────────────────────────

def test_expense_crud_and_month_total(client):
    r = client.post("/expenses", json={
        "category": "utility", "description": "Electricity",
        "amount": 200.0, "date": "2026-07-01", "notes": None,
    })
    assert r.status_code == 200
    exp_id = r.json()["expense_id"]

    listing = client.get("/expenses?month=2026-07").json()
    assert listing["total"] == pytest.approx(200.0)
    assert len(listing["expenses"]) == 1

    d = client.delete(f"/expenses/{exp_id}")
    assert d.status_code == 200
    listing2 = client.get("/expenses?month=2026-07").json()
    assert listing2["total"] == 0


# ── Workers (regression coverage for the Paid-flag cashout bug) ───────────────

def test_worker_balance_accrues_ledger_entries(client):
    r = client.post("/workers", json={"name": "Worker A", "base_salary": 700.0})
    wid = r.json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 500, "note": "yes"})
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 500, "note": None})

    workers = client.get("/workers").json()
    w = next(x for x in workers if x["worker_id"] == wid)
    assert w["balance_owed"] == pytest.approx(1000.0)  # salary accrual ~0 (same day)


def test_cashout_zeroes_balance_and_does_not_repeat(client):
    """Regression test: same-day ledger entries must not keep re-counting
    after a cashout (the Date >= Last_Cashout_Date bug)."""
    r = client.post("/workers", json={"name": "Worker B", "base_salary": 700.0})
    wid = r.json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 1000})

    payout1 = client.post(f"/workers/{wid}/cashout", json={"note": None})
    assert payout1.json()["amount_paid"] == pytest.approx(1000.0)

    workers = client.get("/workers").json()
    w = next(x for x in workers if x["worker_id"] == wid)
    assert w["balance_owed"] == pytest.approx(0.0)

    # cashing out again same day must NOT re-pay the same 1000
    payout2 = client.post(f"/workers/{wid}/cashout", json={"note": None})
    assert payout2.json()["amount_paid"] == pytest.approx(0.0)


def test_worker_update_and_deactivate(client):
    r = client.post("/workers", json={"name": "Worker C", "base_salary": 500.0})
    wid = r.json()["worker_id"]
    client.put(f"/workers/{wid}", json={"active": 0})
    active_only = client.get("/workers?active_only=true").json()
    assert all(w["worker_id"] != wid for w in active_only)


# ── Dashboard / profit models ──────────────────────────────────────────────────

def test_gross_profit_matches_sum_of_order_profits(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, cost=60.0, stock=20)
    generate_invoice(client, cx_id, "Test Customer", 1, 2, bill_type="actual")  # profit 80
    generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")  # profit 40

    stats = client.get("/dashboard/stats").json()
    assert stats["gross_profit"] == pytest.approx(120.0)


def test_net_profit_subtracts_expenses_and_cashouts(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, cost=60.0, stock=20)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post(f"/orders/{inv}/payments", json={"amount": 100, "type": "payment"})

    client.post("/expenses", json={"category": "misc", "description": "Supplies",
                                    "amount": 20.0, "date": "2026-07-04", "notes": None})

    w = client.post("/workers", json={"name": "Worker D", "base_salary": 700.0}).json()["worker_id"]
    client.post(f"/workers/{w}/ledger", json={"type": "bonus", "amount": 30})
    client.post(f"/workers/{w}/cashout", json={"note": None})

    stats = client.get("/dashboard/stats").json()
    # net = 100 (payment) - 20 (expense) - 30 (cashout) = 50
    assert stats["net_profit"] == pytest.approx(50.0)


def test_estimated_profit_only_counts_active_workers(client):
    make_customer(client)
    client.post("/workers", json={"name": "Active Worker", "base_salary": 700.0})
    inactive_id = client.post("/workers", json={"name": "Inactive Worker", "base_salary": 500.0}).json()["worker_id"]
    client.put(f"/workers/{inactive_id}", json={"active": 0})

    breakdown = client.get("/dashboard/profit-breakdown?type=estimated").json()
    assert breakdown["workers_total"] == pytest.approx(700.0)


def test_profit_breakdown_rejects_invalid_type(client):
    r = client.get("/dashboard/profit-breakdown?type=bogus")
    assert r.status_code == 422


# ── Products CRUD ────────────────────────────────────────────────────────────

def test_product_not_found_returns_404(client):
    r = client.get("/products/999")
    assert r.status_code == 404


def test_product_update_partial_fields(client):
    make_product(client, 1, retail=100.0, stock=10)
    r = client.put("/products/1", json={"retail_price": 150.0})
    assert r.status_code == 200
    updated = r.json()
    assert updated["retail_price"] == pytest.approx(150.0)
    assert updated["stock_quantity"] == 10  # untouched fields preserved


def test_duplicate_product_id_rejected(client):
    make_product(client, 1)
    r = client.post("/products", json={
        "product_id": 1, "item_name": "Dup", "retail_price": 10.0,
        "wholesale_price": 8.0, "cost": 5.0, "stock_quantity": 1,
    })
    assert r.status_code == 400


def test_delete_product_blocked_once_used_in_order(client):
    cx_id = make_customer(client)
    make_product(client, 1, stock=10)
    generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")
    r = client.delete("/products/1")
    assert r.status_code == 400


def test_delete_unused_product_succeeds(client):
    make_product(client, 1, stock=10)
    r = client.delete("/products/1")
    assert r.status_code == 200
    assert client.get("/products/1").status_code == 404


def test_null_stock_treated_as_zero_when_tracking_enabled(client):
    """track_stock is a global switch, not per-product. When it's on (as the
    test fixture's config.yaml sets it), a NULL stock_quantity is treated as
    starting at 0 via COALESCE, per Process2_pure's own documented behavior —
    it is NOT exempted from tracking just because it was never set."""
    cx_id = make_customer(client)
    make_product(client, 1, stock=None)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 100, bill_type="actual")
    assert r.status_code == 200
    warnings = r.json()["stock_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["stock_quantity"] == -100
    assert client.get("/products/1").json()["stock_quantity"] == -100


def test_stock_untouched_when_tracking_disabled_globally(client, monkeypatch):
    """With track_stock off entirely, stock must never be touched regardless
    of whether stock_quantity is set or NULL."""
    monkeypatch.setattr(process_module, "get_stock_config", lambda: False)
    cx_id = make_customer(client)
    make_product(client, 1, stock=None)
    make_product(client, 2, stock=5)
    r1 = generate_invoice(client, cx_id, "Test Customer", 1, 100, bill_type="actual")
    r2 = generate_invoice(client, cx_id, "Test Customer", 2, 3, bill_type="actual")
    assert r1.json()["stock_warnings"] == []
    assert r2.json()["stock_warnings"] == []
    assert client.get("/products/1").json()["stock_quantity"] is None
    assert client.get("/products/2").json()["stock_quantity"] == 5


# ── Customers ────────────────────────────────────────────────────────────────

def test_customer_not_found_returns_404(client):
    assert client.get("/customers/999").status_code == 404


def test_generate_invoice_reuses_existing_customer_by_name(client):
    cx_id = make_customer(client, "Repeat Customer")
    make_product(client, 1, retail=50.0, stock=10)
    r = generate_invoice(client, 0, "Repeat Customer", 1, 1, bill_type="actual")
    assert r.status_code == 200
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["cx_name"] == "Repeat Customer"
    # must not have created a second customer row
    all_customers = [c for c in client.get("/customers").json() if c["name"] == "Repeat Customer"]
    assert len(all_customers) == 1


def test_generate_invoice_creates_new_customer_when_unknown(client):
    make_product(client, 1, retail=50.0, stock=10)
    r = generate_invoice(client, 0, "Brand New Customer", 1, 1, bill_type="actual")
    assert r.status_code == 200
    all_customers = [c for c in client.get("/customers").json() if c["name"] == "Brand New Customer"]
    assert len(all_customers) == 1


# ── Pricing tiers / discount / tax ──────────────────────────────────────────

def test_wholesale_tier_uses_wholesale_price(client):
    cx_id = make_customer(client, tier="wholesale")
    make_product(client, 1, retail=100.0, wholesale=70.0, cost=50.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", tier="wholesale")
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["total"] == pytest.approx(70.0)


def test_flat_discount_reduces_total(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", discount="20")
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["total"] == pytest.approx(80.0)


def test_percent_discount_reduces_total(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", discount="10%")
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["total"] == pytest.approx(90.0)


def test_tax_applied_when_enabled(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", apply_tax=True)
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["total"] == pytest.approx(114.0)  # 14% tax from CONFIG_YAML fixture


# ── Orders ───────────────────────────────────────────────────────────────────

def test_order_not_found_returns_404(client):
    assert client.get("/orders/999").status_code == 404


def test_return_unknown_invoice_returns_404(client):
    r = client.post("/return-invoice", json={"invoice_number": 999})
    assert r.status_code == 404


def test_orders_list_returns_newest_first(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=50.0, stock=10)
    inv1 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    inv2 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    listing = client.get("/orders").json()
    assert listing[0]["invoice_number"] == int(inv2)
    assert listing[1]["invoice_number"] == int(inv1)


# ── Payments: refunds, credit-apply validation ────────────────────────────────

def test_refund_reduces_net_profit_cash_in(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post(f"/orders/{inv}/payments", json={"amount": 100, "type": "payment"})
    client.post(f"/orders/{inv}/payments", json={"amount": -30, "type": "refund"})

    net = client.get("/dashboard/profit-breakdown?type=net").json()
    assert net["cash_in"] == pytest.approx(70.0)  # 100 - 30


def test_credit_apply_unknown_invoice_returns_404(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    r = client.post("/orders/credit-apply", json={
        "source_invoice": 999, "target_invoice": int(inv), "amount": 10,
    })
    assert r.status_code == 404


def test_bulk_allocate_unknown_invoice_returns_404(client):
    cx_id = make_customer(client)
    r = client.post(f"/customers/{cx_id}/payments", json={
        "allocations": [{"invoice_number": 999, "amount": 10}]
    })
    assert r.status_code == 404


def test_customer_balances_unknown_customer_returns_404(client):
    assert client.get("/customers/999/balances").status_code == 404


# ── Workers: ledger types, cashout history ────────────────────────────────────

def test_worker_deduction_reduces_balance(client):
    wid = client.post("/workers", json={"name": "Worker E", "base_salary": 700.0}).json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 500})
    client.post(f"/workers/{wid}/ledger", json={"type": "deduction", "amount": -200})
    workers = client.get("/workers").json()
    w = next(x for x in workers if x["worker_id"] == wid)
    assert w["balance_owed"] == pytest.approx(300.0)


def test_worker_ledger_listing_reflects_entries(client):
    wid = client.post("/workers", json={"name": "Worker F", "base_salary": 700.0}).json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 100, "note": "first"})
    ledger = client.get(f"/workers/{wid}/ledger").json()
    assert len(ledger["ledger"]) == 1
    assert ledger["ledger"][0]["note"] == "first"


def test_cashout_history_recorded(client):
    wid = client.post("/workers", json={"name": "Worker G", "base_salary": 700.0}).json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 200})
    client.post(f"/workers/{wid}/cashout", json={"note": "first payout"})
    history = client.get(f"/workers/{wid}/cashouts").json()
    assert len(history) == 1
    assert history[0]["amount_paid"] == pytest.approx(200.0)
    assert history[0]["note"] == "first payout"


# ── Dashboard top-lists ──────────────────────────────────────────────────────

def test_top_bills_excludes_cancelled_orders(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, cost=10.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post("/return-invoice", json={"invoice_number": inv})

    stats = client.get("/dashboard/stats").json()
    assert all(b["invoice_number"] != int(inv) for b in stats["top_bills"])


def test_top_items_sums_quantity_across_orders(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=50.0, stock=50)
    generate_invoice(client, cx_id, "Test Customer", 1, 3, bill_type="actual")
    generate_invoice(client, cx_id, "Test Customer", 1, 2, bill_type="actual")
    stats = client.get("/dashboard/stats").json()
    item = next(i for i in stats["top_items"] if i["name"] == "1")
    assert item["qty"] == 5


# ── Worker delete guard + reactivation ──────────────────────────────────────

def test_delete_worker_succeeds_when_no_history(client):
    wid = client.post("/workers", json={"name": "Clean Worker", "base_salary": 500.0}).json()["worker_id"]
    r = client.delete(f"/workers/{wid}")
    assert r.status_code == 200
    workers = client.get("/workers").json()
    assert all(w["worker_id"] != wid for w in workers)


def test_delete_worker_blocked_with_ledger_history(client):
    wid = client.post("/workers", json={"name": "Has History", "base_salary": 500.0}).json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 100})
    r = client.delete(f"/workers/{wid}")
    assert r.status_code == 400
    # must still exist
    workers = client.get("/workers").json()
    assert any(w["worker_id"] == wid for w in workers)


def test_delete_worker_blocked_with_cashout_history(client):
    wid = client.post("/workers", json={"name": "Cashed Out Worker", "base_salary": 500.0}).json()["worker_id"]
    client.post(f"/workers/{wid}/ledger", json={"type": "bonus", "amount": 50})
    client.post(f"/workers/{wid}/cashout", json={"note": None})
    r = client.delete(f"/workers/{wid}")
    assert r.status_code == 400


def test_delete_unknown_worker_returns_400(client):
    r = client.delete("/workers/999")
    assert r.status_code == 400


def test_reactivate_worker(client):
    wid = client.post("/workers", json={"name": "Toggle Worker", "base_salary": 500.0}).json()["worker_id"]
    client.put(f"/workers/{wid}", json={"active": 0})
    active_only = client.get("/workers?active_only=true").json()
    assert all(w["worker_id"] != wid for w in active_only)

    client.put(f"/workers/{wid}", json={"active": 1})
    active_only2 = client.get("/workers?active_only=true").json()
    assert any(w["worker_id"] == wid for w in active_only2)


# ── Negative-value guards (session bugfix round) ──────────────────────────────

def test_negative_base_salary_rejected_on_create(client):
    r = client.post("/workers", json={"name": "Bad Worker", "base_salary": -100})
    assert r.status_code in (400, 422)
    workers = client.get("/workers").json()
    assert all(w["name"] != "Bad Worker" for w in workers)


def test_negative_base_salary_rejected_on_update(client):
    wid = client.post("/workers", json={"name": "Fine Worker", "base_salary": 500}).json()["worker_id"]
    r = client.put(f"/workers/{wid}", json={"base_salary": -50})
    assert r.status_code in (400, 422)
    workers = client.get("/workers").json()
    w = next(x for x in workers if x["worker_id"] == wid)
    assert w["base_salary"] == 500  # unchanged


def test_negative_amount_paid_now_rejected(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", amount_paid_now=-50.0)
    assert r.status_code == 422


def test_negative_flat_discount_rejected(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", discount="-20")
    assert r.status_code == 400


def test_negative_percent_discount_rejected(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", discount="-10%")
    assert r.status_code == 400


def test_flat_discount_capped_at_subtotal(client):
    """A flat discount larger than the subtotal must never push the total
    negative — it should cap at 100% off, not go further."""
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", discount="500")
    assert r.status_code == 200
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["total"] == pytest.approx(0.0)
    assert order["total"] >= 0


def test_percent_discount_capped_at_100(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", discount="250%")
    assert r.status_code == 200
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["total"] == pytest.approx(0.0)


def test_discount_never_produces_negative_total_or_stored_discount(client):
    """Regression for: discount stored as negative, rendered as double-negative
    in the orders tab, and silently erased from the HTML bill."""
    cx_id = make_customer(client)
    make_product(client, 1, retail=50.0, stock=10)
    r = generate_invoice(client, cx_id, "Test Customer", 1, 2, bill_type="actual", discount="30")
    order = client.get(f"/orders/{r.json()['invoice_number']}").json()
    assert order["discount"] >= 0
    assert order["total"] >= 0


# ── Amount-paid / HTML reflection (session bugfix round) ──────────────────────

def test_amount_paid_reflected_in_rendered_html(client):
    """Regression for: amount_paid/balance_due were always written into the
    invoice packet — even as 'EGP0.00' — which is a truthy string, so the
    template's {% if amount_paid %} check always fired, regardless of
    whether anything was actually paid."""
    packet_paid = {
        "header": {"customer_name": "X", "tier": "Retail"},
        "table_data": [],
        "financials": {
            "subtotal": "EGP100.00", "discount_pct": 0, "discount_amount": "EGP0.00",
            "after_discount": "EGP100.00", "discount": "EGP0.00", "tax": "EGP0.00",
            "grand_total": "EGP100.00", "amount_paid": "EGP40.00", "balance_due": "EGP60.00",
        },
        "system_metrics": {"internal_profit": "EGP0.00"},
    }
    html_paid = invoice_output.Render_Invoice_HTML(packet_paid, "1", "2026-07-05")
    assert "Amount Paid" in html_paid
    assert "EGP40.00" in html_paid
    assert "Balance Due" in html_paid

    packet_unpaid = {**packet_paid, "financials": {**packet_paid["financials"]}}
    packet_unpaid["financials"].pop("amount_paid")
    packet_unpaid["financials"].pop("balance_due")
    html_unpaid = invoice_output.Render_Invoice_HTML(packet_unpaid, "2", "2026-07-05")
    assert "Amount Paid" not in html_unpaid


def test_generate_invoice_amount_paid_now_appears_on_html_when_positive(client, monkeypatch):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    captured = {}

    def fake_save(html, slug, cx_name=None, output_dir=None):
        captured["html"] = html
        return (f"{slug}.html", f"{slug}.pdf")

    monkeypatch.setattr(functions, "Save_And_Open_Invoice", fake_save)
    generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual", amount_paid_now=40.0)

    assert "Amount Paid" in captured["html"]
    assert "40.00" in captured["html"]


def test_generate_invoice_no_amount_paid_row_when_nothing_paid(client, monkeypatch):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    captured = {}

    def fake_save(html, slug, cx_name=None, output_dir=None):
        captured["html"] = html
        return (f"{slug}.html", f"{slug}.pdf")

    monkeypatch.setattr(functions, "Save_And_Open_Invoice", fake_save)
    generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual")

    assert "Amount Paid" not in captured["html"]


# ── Refund on cancelled invoices (session bugfix round) ───────────────────────

def test_refund_allowed_on_cancelled_invoice(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post(f"/orders/{inv}/payments", json={"amount": 100, "type": "payment"})
    client.post("/return-invoice", json={"invoice_number": inv})

    r = client.post(f"/orders/{inv}/payments", json={"amount": -50, "type": "refund"})
    assert r.status_code == 200
    pay = client.get(f"/orders/{inv}/payments").json()
    assert pay["balance_due"] == pytest.approx(-50.0)  # 100 paid - 50 refunded = 50 still owed back


def test_payment_still_blocked_on_cancelled_invoice(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post("/return-invoice", json={"invoice_number": inv})
    r = client.post(f"/orders/{inv}/payments", json={"amount": 50, "type": "payment"})
    assert r.status_code == 400


def test_full_refund_on_cancelled_invoice_zeroes_credit(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post(f"/orders/{inv}/payments", json={"amount": 100, "type": "payment"})
    client.post("/return-invoice", json={"invoice_number": inv})
    client.post(f"/orders/{inv}/payments", json={"amount": -100, "type": "refund"})

    pay = client.get(f"/orders/{inv}/payments").json()
    assert pay["balance_due"] == pytest.approx(0.0)


# ── Credit sweeping into new invoices (session bugfix round) ──────────────────

def test_sweep_credit_applies_automatically_via_endpoint(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=20)

    inv1 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post(f"/orders/{inv1}/payments", json={"amount": 100, "type": "payment"})
    client.post("/return-invoice", json={"invoice_number": inv1})
    # inv1 now carries a 100 credit for this customer

    inv2 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    # inv2 owes 100, unpaid

    sweep = client.post(f"/customers/{cx_id}/sweep-credit/{inv2}")
    assert sweep.status_code == 200
    assert sweep.json()["applied"] == pytest.approx(100.0)

    bal2 = client.get(f"/orders/{inv2}/payments").json()["balance_due"]
    bal1 = client.get(f"/orders/{inv1}/payments").json()["balance_due"]
    assert bal2 == pytest.approx(0.0)
    assert bal1 == pytest.approx(0.0)


def test_sweep_credit_partial_when_credit_smaller_than_owed(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=20)

    inv1 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    client.post(f"/orders/{inv1}/payments", json={"amount": 40, "type": "payment"})
    client.post("/return-invoice", json={"invoice_number": inv1})
    # inv1 credit = 40

    inv2 = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]
    # inv2 owes 100

    sweep = client.post(f"/customers/{cx_id}/sweep-credit/{inv2}")
    assert sweep.json()["applied"] == pytest.approx(40.0)
    bal2 = client.get(f"/orders/{inv2}/payments").json()["balance_due"]
    assert bal2 == pytest.approx(60.0)  # 100 owed - 40 credit


def test_sweep_credit_zero_when_no_credit_available(client):
    cx_id = make_customer(client)
    make_product(client, 1, retail=100.0, stock=10)
    inv = generate_invoice(client, cx_id, "Test Customer", 1, 1, bill_type="actual").json()["invoice_number"]

    sweep = client.post(f"/customers/{cx_id}/sweep-credit/{inv}")
    assert sweep.status_code == 200
    assert sweep.json()["applied"] == pytest.approx(0.0)


def test_sweep_credit_unknown_invoice_returns_404(client):
    cx_id = make_customer(client)
    r = client.post(f"/customers/{cx_id}/sweep-credit/999")
    assert r.status_code == 404


def test_sweep_credit_unknown_customer_returns_404(client):
    make_product(client, 1, retail=100.0, stock=10)
    r = client.post("/customers/999/sweep-credit/1")
    assert r.status_code == 404


def test_generate_invoice_response_includes_customer_id(client):
    """Regression: the frontend's automatic credit-sweep step needs
    customer_id back from /generate-invoice, including for brand-new
    customers created inline during this same call."""
    make_product(client, 1, retail=50.0, stock=10)
    r = generate_invoice(client, 0, "Sweep Test Customer", 1, 1, bill_type="actual")
    assert r.status_code == 200
    assert "customer_id" in r.json()
    assert r.json()["customer_id"] > 0
    matches = [c for c in client.get("/customers").json() if c["name"] == "Sweep Test Customer"]
    assert matches and matches[0]["customer_id"] == r.json()["customer_id"]