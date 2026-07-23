import datetime
import sqlite3


def _ensure_notes_column(c: sqlite3.Cursor): # decided to add a notes column to the expenses table, but this function ensures it exists before any read/write operations as the og schema didn't have it
    try: 
        c.execute("ALTER TABLE Expenses ADD COLUMN Notes TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists


def get_all_expenses_pure(c: sqlite3.Cursor, month: str | None = None):
    """Returns rows as (expense_id, category, description, amount, date, notes)."""
    _ensure_notes_column(c)
    if month:
        c.execute(
            """SELECT Expense_ID, Category, Description, Amount, Date_Added, Notes
               FROM Expenses WHERE Month = ? ORDER BY Date_Added DESC""",
            (month,),
        )
    else:
        c.execute(
            """SELECT Expense_ID, Category, Description, Amount, Date_Added, Notes
               FROM Expenses ORDER BY Month DESC, Date_Added DESC"""
        )
    return c.fetchall()


def get_expense_total_pure(c: sqlite3.Cursor, month: str | None = None) -> float:
    if month:
        c.execute("SELECT COALESCE(SUM(Amount), 0) FROM Expenses WHERE Month = ?", (month,))
    else:
        c.execute("SELECT COALESCE(SUM(Amount), 0) FROM Expenses")
    return c.fetchone()[0]


def add_expense_pure(c: sqlite3.Cursor, category: str, description: str,
                      amount: float, date: str, notes: str | None) -> int:
    """`date` is 'YYYY-MM-DD'; Month is derived as the first 7 chars."""
    _ensure_notes_column(c)
    month = date[:7]
    c.execute(
        """INSERT INTO Expenses (Category, Description, Amount, Month, Date_Added, Notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (category, description, abs(amount), month, date, notes),
    )
    return c.lastrowid


def delete_expense_pure(c: sqlite3.Cursor, expense_id: int):
    c.execute("DELETE FROM Expenses WHERE Expense_ID = ?", (expense_id,))
    if c.rowcount == 0:
        raise ValueError(f"Expense {expense_id} not found")
