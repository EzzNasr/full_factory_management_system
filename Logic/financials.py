from .db import get_tax_config, set_tax_config


#  Pure calculation functions 


def fmt(value: float) -> str:
    """EGP with comma thousands separator. e.g. 12450.5 → 'EGP 12,450.50'"""
    return f"EGP {value:,.2f}"


def Calculate_Subtotal(final_cart):
    """Sums index 3 (line price) from every cart item."""
    return sum(item[3] for item in final_cart)


def Calculate_Profit(final_cart, subtotal, discount_amount):
    """Sums index 2 (line cost). Profit = revenue after discount - total cost."""
    total_order_cost = sum(item[2] for item in final_cart)
    actual_revenue   = subtotal - discount_amount
    final_profit     = actual_revenue - total_order_cost
    return final_profit, total_order_cost


def Calculate_Financials_pure(final_cart, discount_percentage, apply_tax, tax_rate):
    subtotal         = sum(item[3] for item in final_cart)
    discount_amount  = subtotal * (discount_percentage / 100)
    after_discount   = subtotal - discount_amount
    tax_amount       = after_discount * tax_rate if apply_tax else 0
    grand_total      = after_discount + tax_amount
    profit, total_order_cost = Calculate_Profit(final_cart, subtotal, discount_amount)
    return {
        "subtotal":        subtotal,
        "discount_amount": discount_amount,
        "tax_amount":      tax_amount,
        "grand_total":     grand_total,
        "profit":          profit,
        "total_order_cost": total_order_cost,
    }


def Package_Invoice_Data(cx_name, tier, final_cart, subtotal, discount_amount,
                         discount_pct, tax_amount, grand_total, profit):
    """Transforms raw checkout data into GUI-ready string formats."""
    gui_table_data = []
    for item in final_cart:
        p_id, qty, line_cost, line_total, p_name = item
        unit_price = line_total / qty
        gui_table_data.append(
            [str(p_id), str(qty), fmt(unit_price), fmt(line_total), p_name]
        )

    after_discount_val = subtotal - discount_amount

    return {
        "header": {
            "customer_name": cx_name,
            "tier":          tier.capitalize(),
        },
        "table_data": gui_table_data,
        "financials": {
            "subtotal":        fmt(subtotal),
            "discount_pct":    discount_pct,
            "discount_amount": fmt(discount_amount),
            "after_discount":  fmt(after_discount_val),
            "discount":        fmt(-discount_amount),
            "tax":             fmt(tax_amount),
            "grand_total":     fmt(grand_total),
        },
        "system_metrics": {
            "internal_profit": fmt(profit),
        },
    }


#  CLI wrappers 

def Apply_Discount(subtotal):
    print(f"\n--- Discount Phase ---")
    print(f"Current Subtotal: {fmt(subtotal)}")
    while True:
        raw_disc = input("Enter discount (e.g., '10%', '50', or '0' to skip): ").strip()
        if not raw_disc or raw_disc == '0':
            return subtotal, 0.0, 0.0
        if raw_disc.endswith('%'):
            try:
                perc = float(raw_disc[:-1])
                if 0 <= perc <= 100:
                    discount_amt = subtotal * (perc / 100)
                    return subtotal - discount_amt, discount_amt, perc
            except ValueError:
                pass
        else:
            try:
                flat = float(raw_disc)
                if 0 <= flat <= subtotal:
                    return subtotal - flat, flat, 0.0
                elif flat > subtotal:
                    print("Error: Discount cannot be greater than the subtotal")
                    continue
            except ValueError:
                pass
        print("Invalid input. Please enter a valid number (e.g., 20) or percentage (e.g., 15%).")


def Apply_Taxes(current_total):
    apply_tax, tax_rate = get_tax_config()
    status_label = f"ON  ({int(round(tax_rate * 100))}%)" if apply_tax else "OFF"
    print(f"\n--- Tax Phase ---")
    print(f"  Tax is currently: {status_label}")
    toggle = input("  Press T to toggle tax ON/OFF, or Enter to keep as-is: ").strip().lower()
    if toggle == "t":
        apply_tax, tax_rate = set_tax_config(not apply_tax)
        new_label = f"ON  ({int(round(tax_rate * 100))}%)" if apply_tax else "OFF"
        print(f"  ✅ Tax toggled → {new_label}  (config.yaml updated)")
    if apply_tax and tax_rate > 0:
        tax_amount  = current_total * tax_rate
        final_total = current_total + tax_amount
        return final_total, tax_amount, tax_rate
    else:
        return current_total, 0.0, 0.0
