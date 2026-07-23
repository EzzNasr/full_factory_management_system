import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Logic import functions
from Logic import Tables
from Logic.routers import (
    customers_router,
    products_router,
    orders_router,
    dashboard_router,
    expenses_router,
    workers_router,
    payments_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = sqlite3.connect(functions.DB_PATH)
    Tables.ensure_schema(conn)
    conn.close()
    yield


app = FastAPI(title="Full Factory Management System API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers_router.router)
app.include_router(products_router.router)
app.include_router(orders_router.router)
app.include_router(dashboard_router.router)
app.include_router(expenses_router.router)
app.include_router(workers_router.router)
app.include_router(payments_router.router)


# Run: python -m uvicorn Logic.fastapi_app:app --reload