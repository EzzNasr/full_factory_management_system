import sqlite3
from Logic import functions


#  DB dependency 

def get_db():
    conn = sqlite3.connect(functions.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
