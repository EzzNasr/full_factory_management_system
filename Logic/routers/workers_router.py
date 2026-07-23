import sqlite3

from fastapi import APIRouter, HTTPException, Depends

from Logic import workers as wrk_module
from Logic.dependencies import get_db
from Logic.schemas import WorkerCreate, WorkerUpdate, LedgerEntryCreate, CashoutCreate

router = APIRouter()


#  Worker endpoints 

@router.get("/workers")
async def get_all_workers(active_only: bool = False, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    rows = wrk_module.get_all_workers_pure(c, active_only)
    result = []
    for r in rows:
        worker_id, name, base_salary, active = r
        balance = wrk_module.get_worker_balance_pure(c, worker_id)
        result.append({
            "worker_id": worker_id, "name": name,
            "base_salary": base_salary, "active": active,
            "balance_owed": balance,
        })
    return result

@router.post("/workers")
async def add_worker(worker: WorkerCreate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    worker_id = wrk_module.add_worker_pure(c, worker.name, worker.base_salary)
    db.commit()
    return {"message": "Worker added.", "worker_id": worker_id}

@router.put("/workers/{worker_id}")
async def update_worker(worker_id: int, worker: WorkerUpdate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    fields = worker.dict(exclude_unset=True)
    wrk_module.update_worker_pure(c, worker_id, **fields)
    db.commit()
    return {"message": f"Worker {worker_id} updated."}

@router.get("/workers/{worker_id}/ledger")
async def get_worker_ledger(worker_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    rows = wrk_module.get_worker_ledger_pure(c, worker_id)
    balance = wrk_module.get_worker_balance_pure(c, worker_id)
    return {
        "worker_id": worker_id,
        "balance_owed": balance,
        "ledger": [
            {"ledger_id": r[0], "date": r[1], "type": r[2], "amount": r[3], "note": r[4]}
            for r in rows
        ],
    }

@router.delete("/workers/{worker_id}")
async def delete_worker(worker_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    try:
        wrk_module.delete_worker_pure(c, worker_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"message": f"Worker {worker_id} deleted."}

@router.post("/workers/{worker_id}/ledger")
async def add_ledger_entry(worker_id: int, entry: LedgerEntryCreate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    ledger_id = wrk_module.add_ledger_entry_pure(
        c, worker_id, entry.type, entry.amount, entry.note, entry.date
    )
    db.commit()
    return {"message": "Ledger entry added.", "ledger_id": ledger_id}

@router.post("/workers/{worker_id}/cashout")
async def cashout_worker(worker_id: int, cashout: CashoutCreate, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    amount_paid = wrk_module.cashout_worker_pure(c, worker_id, cashout.note)
    db.commit()
    return {"message": f"Worker {worker_id} paid out.", "amount_paid": amount_paid}

@router.get("/workers/{worker_id}/cashouts")
async def get_worker_cashouts(worker_id: int, db: sqlite3.Connection = Depends(get_db)):
    c = db.cursor()
    rows = wrk_module.get_all_cashouts_pure(c, worker_id)
    return [{"cashout_id": r[0], "date": r[2], "amount_paid": r[3], "note": r[4]} for r in rows]
