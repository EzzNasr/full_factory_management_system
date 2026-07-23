import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends

from Logic import expenses as exp_module
from Logic.dependencies import get_db
from Logic.schemas import ExpenseCreate

router = APIRouter()


#  Expense endpoints 

@router.get("/expenses")
async def get_expenses(month: Optional[str] = None, db: sqlite3.Connection = Depends(get_db)):
    """Returns expenses filtered by month ('YYYY-MM') or all-time if omitted."""
    c = db.cursor()
    rows = exp_module.get_all_expenses_pure(c, month)
    total = exp_module.get_expense_total_pure(c, month)
    return {
        "expenses": [
            {"expense_id": r[0], "category": r[1], "description": r[2],
             "amount": r[3], "date": r[4], "notes": r[5]} for r in rows
        ],
        "total": total,
        "month": month or "all-time",
    }

@router.post("/expenses")
async def add_expense(expense: ExpenseCreate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    expense_id = exp_module.add_expense_pure(
        c, expense.category, expense.description,
        expense.amount, expense.date, expense.notes
    )
    db.commit()
    return {"message": "Expense added.", "expense_id": expense_id}

@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    exp_module.delete_expense_pure(c, expense_id)
    db.commit()
    return {"message": f"Expense {expense_id} deleted."}
