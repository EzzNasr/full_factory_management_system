import sqlite3
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from Logic import functions
from Logic.dependencies import get_db
from Logic.schemas import Product, ProductCreate, ProductUpdate

router = APIRouter()


#  Product endpoints 

@router.get("/products", response_model=List[Product])
async def get_all_products(db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    return [dict(r) for r in functions.get_all_products_pure(c)]

@router.get("/products/{product_id}", response_model=Product)
async def get_product_details(product_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    row = functions.get_product_details_pure(c, product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return dict(row)

@router.post("/products", response_model=Product)
async def create_product(product: ProductCreate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    try:
        functions.insert_new_product_pure(
            c, db, product.product_id, product.item_name,
            product.retail_price, product.wholesale_price,
            cost=product.cost, stock_quantity=product.stock_quantity
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Product ID {product.product_id} already exists.")
    return dict(functions.get_product_details_pure(c, product.product_id))

@router.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: int, product: ProductUpdate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    updated = functions.update_product_pure(c, db, product_id, **product.dict(exclude_unset=True))
    db.commit()
    return dict(updated)

@router.delete("/products/{product_id}")
async def delete_product(product_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    functions.delete_product_pure(c, db, product_id)
    db.commit()
    return {"message": f"Product {product_id} deleted."}
