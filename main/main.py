import sys
import os
import sqlite3
from Logic import functions
from Logic import Tables


# main.py lives in  .../full_factory_management_system/main/

# functions.py lives in  .../full_factory_management_system/Logic/


_MAIN_DIR     = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_MAIN_DIR)
_LOGIC_DIR    = os.path.join(_PROJECT_ROOT, "Logic")


if _LOGIC_DIR not in sys.path:
    sys.path.insert(0, _LOGIC_DIR)


# main.py  Entry point for The ERP 

# All logic lives in Logic/... 

#where functions.py calles the needed functions from thee other modules in Logic/...

def main():
    # Creates every table (and any columns added after the original
    # CREATE TABLE) if they don't already exist. Safe to call every run 
    # this is the only entry point for the terminal CLI, so it has to set
    # up the schema itself rather than relying on the FastAPI process.
    conn = sqlite3.connect(functions.DB_PATH)
    Tables.ensure_schema(conn)
    conn.close()

    functions.bill_type()

if __name__ == "__main__":
    main()