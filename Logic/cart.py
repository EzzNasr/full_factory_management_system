from fastapi import HTTPException


#  Pure functions (for FastAPI) 


def Bulk_system_pure(valid_products, tier :str , bulk_qty: int ):
    """handling bulk choice by user and calculating the total cost and price for each product based on the tier (retail or wholesale) and the quantities provided."""
    final_order_details = []
    for prod in valid_products:
        p_id, p_name, p_retail, p_wholesale, p_cost = prod
        active_price    = p_wholesale if tier.strip().lower() == "wholesale" else p_retail
        total_line_cost = p_cost * bulk_qty
        final_line_price = active_price * bulk_qty
        final_order_details.append((p_id, bulk_qty, total_line_cost, final_line_price, p_name))
    return final_order_details


def Individual_system_pure(valid_products, tier: str, quantities: dict):
    """handling individual choice by user and calculating the total cost and price for each product based on the tier (retail or wholesale) and the quantities provided."""

    final_order_details = []
    for prod in valid_products:
        p_id, p_name, p_retail, p_wholesale, p_cost = prod
        active_price = p_wholesale if tier.strip().lower() == "wholesale" else p_retail
        qty = quantities.get(p_id)
        if qty is None or qty <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Quantity for product {p_name} (ID: {p_id}) is missing or invalid."
            )
        total_line_cost  = p_cost * qty
        final_line_price = active_price * qty
        final_order_details.append((p_id, qty, total_line_cost, final_line_price, p_name))
    return final_order_details


def parse_discount_input(raw: str, subtotal: float) -> float:
    """Returns a discount PERCENTAGE (0-100), always non-negative, always
    capped so the resulting discount amount can never exceed the subtotal."""
    raw = (raw or "0").strip()
    if raw.startswith("-"):
        raise HTTPException(status_code=400, detail="Discount cannot be negative.")
    if raw.endswith("%"):
        pct = float(raw[:-1] or 0)
        if pct < 0:
            raise HTTPException(status_code=400, detail="Discount percentage cannot be negative.")
        return min(pct, 100.0)
    flat = float(raw or 0)
    if flat < 0:
        raise HTTPException(status_code=400, detail="Discount amount cannot be negative.")
    if subtotal <= 0:
        return 0.0
    flat = min(flat, subtotal)  # cap flat discount at the subtotal itself
    return (flat / subtotal) * 100


# ── CLI versions ──────────────────────────────────────────────────────────────

def Bulk_system(valid_products, tier):
    while True:
        raw_qty = input("Enter the bulk quantity for ALL items: ").strip()
        if raw_qty.isdigit() and int(raw_qty) > 0:
            bulk_qty = int(raw_qty)
            break
        print("Invalid input. Please enter a positive whole number.")

    final_order_details = []
    for prod in valid_products:
        p_id, p_name, p_retail, p_wholesale, p_cost = prod
        active_price     = p_wholesale if tier.strip().lower() == "wholesale" else p_retail
        total_line_cost  = p_cost * bulk_qty
        final_line_price = active_price * bulk_qty
        final_order_details.append((p_id, bulk_qty, total_line_cost, final_line_price, p_name))
    return final_order_details


def Individual_system(valid_products, tier):
    final_order_details = []
    print(f"\nLet's set the quantities for each item.")
    for prod in valid_products:
        p_id, p_name, p_retail, p_wholesale, p_cost = prod
        active_price = p_wholesale if tier.strip().lower() == "wholesale" else p_retail
        while True:
            raw_qty = input(f"Enter quantity for '{p_name}' (ID: {p_id}) @ EGP {active_price:.2f}: ").strip()
            if raw_qty.isdigit() and int(raw_qty) > 0:
                item_qty = int(raw_qty)
                break
            print("Invalid input. Please enter a positive whole number.")
        final_line_price = active_price * item_qty
        total_line_cost  = p_cost * item_qty
        final_order_details.append((p_id, item_qty, total_line_cost, final_line_price, p_name))
    return final_order_details


def Quantity_System(valid_products, tier):
    while True:
        choice = input("\nPress 1 for Bulk Quantity or 2 for Individual Quantity: ").strip()
        if choice == '1':
            print("\n--- Bulk Quantity Mode ---")
            return Bulk_system(valid_products, tier)
        elif choice == '2':
            print("\n--- Individual Quantity Mode ---")
            return Individual_system(valid_products, tier)
        else:
            print("Invalid choice. Please literally just press 1 or 2.")