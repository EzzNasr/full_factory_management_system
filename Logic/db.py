import os
import sqlite3
import yaml

# Constants that are used through out the project 

# db.py lives in the sub Folder logic of the parent folder ( the_invoice_app_V2 \Logic\db.py)



_LOGIC_DIR    = os.path.dirname(os.path.abspath(__file__))


_PROJECT_ROOT = os.path.dirname(_LOGIC_DIR)


DB_PATH       = os.path.join(_PROJECT_ROOT, "main",  "MasterDB.db")
CONFIG_PATH   = os.path.join(_PROJECT_ROOT, "main",  "config.yaml")
TEMPLATE_PATH = os.path.join(_LOGIC_DIR,             "invoice_template.html")
INVOICES_DIR  = os.path.join(_PROJECT_ROOT,          "invoices")
ASSETS_DIR    = os.path.join(_PROJECT_ROOT,          "assets")



# the bellow functions do not write to the DB , only reading , and the get tax config() function reads the config.yaml file and returns the tax settings.
# The set_tax_config() function rewrites the config.yaml file with new tax settings.

# Process2 (used to update the DB) opens its own dedicated write connection 


conn = sqlite3.connect(DB_PATH)
c    = conn.cursor()


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def get_tax_config():

    # Reads config.yaml, returns a tuple (apply_tax: bool, tax_rate: float).
    # if unable to read config.yaml, returns (False for the tax setting, 0.14 for the tax rate) as default values.

    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
        ts = cfg.get("tax_settings", {})
        return bool(ts.get("apply_tax", False)), float(ts.get("tax_rate", 0.14))
    except Exception:
        return False, 0.14


def set_tax_config(apply_tax: bool, tax_rate: float = None):

    # Rewrites config.yaml with new tax settings. Returns (apply_tax, tax_rate), to save defaults later on 
    # if no tax_rate is provided, the current tax rate is preserved. If config.yaml does not exist, it will be created with the provided settings.

    current_apply, current_rate = get_tax_config()
    final_rate = tax_rate if tax_rate is not None else current_rate
    config_block = (
        f"# config.yaml\n"
        f"tax_settings:\n"
        f"  apply_tax: {'true' if apply_tax else 'false'}\n"
        f"  tax_rate: {final_rate:.2f}  # e.g. 0.14 = 14%\n"
    )
    with open(CONFIG_PATH, "w") as f:
        f.write(config_block)
    return apply_tax, final_rate

def get_stock_config():
    """Reads config.yaml, returns track_stock: bool. Defaults to False if unreadable/missing."""
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
        ss = cfg.get("stock_settings", {})
        return bool(ss.get("track_stock", False))
    except Exception:
        return False