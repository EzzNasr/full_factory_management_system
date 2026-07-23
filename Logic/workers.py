"""
Logic/workers.py

Pure functions backing the /workers endpoints in fastapi_app.py.

FIXME 
DONE  

balance calculation previously used
`WHERE Date >= Last_Cashout_Date` to decide which ledger entries counted
toward the owed balance. Since Date has no time component, entries logged
the same day as a cashout could never be excluded , cashing out just reset
Last_Cashout_Date to today, but today's entries were still >= today, so
they kept re-counting forever.

Replaced with an explicit `Paid` flag on WorkerLedger: cashout marks every
currently-unpaid entry as paid, and the balance calc simply sums unpaid
entries. Salary still accrues separately via Last_Cashout_Date proration.

Schema is created by Tables.ensure_schema(conn), called once at app
startup , see Tables.py. This module assumes Workers, WorkerLedger, and
WorkerCashouts (including the Active and Paid columns) already exist by
the time any function here runs.
"""

import datetime
import sqlite3


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _prorated_salary(base_salary: float, last_cashout_date: str) -> float:
    days = (datetime.datetime.now() - datetime.datetime.strptime(last_cashout_date, "%Y-%m-%d")).days
    days = max(days, 0)
    return round((base_salary / 30.0) * days, 2)


def get_all_workers_pure(c: sqlite3.Cursor, active_only: bool = False):
    if active_only:
        c.execute("SELECT Worker_ID, Name, Base_Salary, Active FROM Workers WHERE Active = 1 ORDER BY Name")
    else:
        c.execute("SELECT Worker_ID, Name, Base_Salary, Active FROM Workers ORDER BY Name")
    return c.fetchall()


def get_worker_balance_pure(c: sqlite3.Cursor, worker_id: int) -> float:
    c.execute("SELECT Base_Salary, Last_Cashout_Date FROM Workers WHERE Worker_ID = ?", (worker_id,))
    row = c.fetchone()
    if not row:
        raise ValueError(f"Worker {worker_id} not found")
    base_salary, last_cashout_date = row[0], row[1]

    accrued = _prorated_salary(base_salary, last_cashout_date)

    c.execute(
        "SELECT COALESCE(SUM(Amount), 0) FROM WorkerLedger WHERE Worker_ID = ? AND Paid = 0",
        (worker_id,),
    )
    ledger_total = c.fetchone()[0]

    return round(accrued + ledger_total, 2)


def add_worker_pure(c: sqlite3.Cursor, name: str, base_salary: float) -> int:
    if base_salary < 0:
        raise ValueError("Base salary cannot be negative.")
    c.execute(
        "INSERT INTO Workers (Name, Base_Salary, Last_Cashout_Date, Active) VALUES (?, ?, ?, 1)",
        (name, base_salary, _today()),
    )
    return c.lastrowid


def update_worker_pure(c: sqlite3.Cursor, worker_id: int, **fields):
    if not fields:
        return
    if "base_salary" in fields and fields["base_salary"] is not None and fields["base_salary"] < 0:
        raise ValueError("Base salary cannot be negative.")
    column_map = {"name": "Name", "base_salary": "Base_Salary", "active": "Active"}
    set_clauses, values = [], []
    for key, value in fields.items():
        column = column_map.get(key)
        if column is None:
            continue
        set_clauses.append(f"{column} = ?")
        values.append(value)
    if not set_clauses:
        return
    values.append(worker_id)
    c.execute(f"UPDATE Workers SET {', '.join(set_clauses)} WHERE Worker_ID = ?", values)
    if c.rowcount == 0:
        raise ValueError(f"Worker {worker_id} not found")


def get_worker_ledger_pure(c: sqlite3.Cursor, worker_id: int):
    """Returns rows as (ledger_id, date, type, amount, note)."""
    c.execute(
        "SELECT Ledger_ID, Date, Type, Amount, Note FROM WorkerLedger WHERE Worker_ID = ? ORDER BY Date DESC",
        (worker_id,),
    )
    return c.fetchall()


def add_ledger_entry_pure(c: sqlite3.Cursor, worker_id: int, type: str,
                           amount: float, note: str | None, date: str | None) -> int:
    entry_date = date or _today()
    c.execute(
        "INSERT INTO WorkerLedger (Worker_ID, Date, Type, Amount, Note, Paid) VALUES (?, ?, ?, ?, ?, 0)",
        (worker_id, entry_date, type, amount, note),
    )
    return c.lastrowid


def cashout_worker_pure(c: sqlite3.Cursor, worker_id: int, note: str | None) -> float:
    """Pays out the current balance, marks all unpaid ledger entries as paid,
    logs the cashout, and resets the salary-accrual clock."""
    amount_paid = get_worker_balance_pure(c, worker_id)
    today = _today()

    c.execute("UPDATE WorkerLedger SET Paid = 1 WHERE Worker_ID = ? AND Paid = 0", (worker_id,))

    c.execute(
        "INSERT INTO WorkerCashouts (Worker_ID, Date, Amount_Paid, Note) VALUES (?, ?, ?, ?)",
        (worker_id, today, amount_paid, note),
    )
    c.execute("UPDATE Workers SET Last_Cashout_Date = ? WHERE Worker_ID = ?", (today, worker_id))
    return amount_paid


def get_all_cashouts_pure(c: sqlite3.Cursor, worker_id: int):
    """Returns rows as (cashout_id, worker_id, date, amount_paid, note)."""
    c.execute(
        "SELECT Cashout_ID, Worker_ID, Date, Amount_Paid, Note FROM WorkerCashouts WHERE Worker_ID = ? ORDER BY Date DESC",
        (worker_id,),
    )
    return c.fetchall()


def delete_worker_pure(c: sqlite3.Cursor, worker_id: int):
    """Hard-delete, but only if the worker has no payroll history at all 
    otherwise this would either orphan or silently erase ledger/cashout
    records. so we Use the flag (update_worker_pure) to remove a worker
    from active lists while preserving their history instead."""
    c.execute("SELECT COUNT(*) FROM WorkerLedger WHERE Worker_ID = ?", (worker_id,))
    ledger_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM WorkerCashouts WHERE Worker_ID = ?", (worker_id,))
    cashout_count = c.fetchone()[0]
    if ledger_count > 0 or cashout_count > 0:
        raise ValueError(
            f"Cannot delete worker {worker_id}: has {ledger_count} ledger entr(y/ies) "
            f"and {cashout_count} cashout(s). Deactivate instead to preserve history."
        )
    c.execute("DELETE FROM Workers WHERE Worker_ID = ?", (worker_id,))
    if c.rowcount == 0:
        raise ValueError(f"Worker {worker_id} not found")