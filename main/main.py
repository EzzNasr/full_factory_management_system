import sys
import os
from Logic import functions


# main.py lives in  .../full_factory_management_system/main/

# functions.py lives in  .../full_factory_management_system/Logic/


_MAIN_DIR     = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_MAIN_DIR)
_LOGIC_DIR    = os.path.join(_PROJECT_ROOT, "Logic")


if _LOGIC_DIR not in sys.path:
    sys.path.insert(0, _LOGIC_DIR)


# main.py — Entry point for The ERP 

# All logic lives in Logic/... 

#where functions.py calles the needed functions from thee other modules in Logic/...

def main():
    functions.bill_type()

if __name__ == "__main__":
    main()
