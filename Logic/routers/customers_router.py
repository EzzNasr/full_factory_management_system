import sqlite3
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from Logic import functions
from Logic.dependencies import get_db
from Logic.schemas import Customer, CustomerCreate

router = APIRouter()


#  Customer endpoints 

@router.get("/customers", response_model=List[Customer])
async def get_all_customers(db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    return [{"customer_id": r[0], "name": r[1], "default_tier": r[2]}
            for r in functions.get_customer_list_pure(c)]

@router.get("/customers/{customer_id}", response_model=Customer)
async def get_customer_by_id(customer_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    row = functions.get_customer_by_id_pure(c, customer_id)
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"customer_id": row[0], "name": row[1], "default_tier": row[2]}

@router.post("/customers", response_model=Customer)
async def create_customer(customer: CustomerCreate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    try:
        row = functions.create_new_customer_pure(c, db, customer.name, customer.phone_number, customer.default_tier)
        db.commit()
        return {"customer_id": row[0], "name": row[1], "default_tier": row[2]}
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database error: {e}")
