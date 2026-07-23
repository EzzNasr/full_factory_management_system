from .db import c, conn

# NOTE: Global convention , if new cx then  id  = 0 is the flag
# any function *_pure is made for API calls  


def Current_Tier_logic(cx_id, cx_name, default_tier, choice):

    """Pure tier decision. Raises ValueError on bad input , default tier = wholsale | retial , choice =1 for keeping default"""

    if cx_id != 0:
        current_tier = default_tier.strip().lower()
        if choice == "1": # for terminal prototyping , 1 is for keep default 
            return (cx_id, cx_name, current_tier)
        elif choice == "2": # change tier choice 
            new_tier = "wholesale" if current_tier == "retail" else "retail"
            return (cx_id, cx_name, new_tier)
        else:
            raise ValueError("Invalid choice. Please enter 1 or 2.")
    else:
        if choice == "1":
            return (cx_id, cx_name, "retail")
        elif choice == "2":
            return (cx_id, cx_name, "wholesale")
        else:
            raise ValueError("Invalid choice. Please enter 1 or 2.")




def get_customer_list():
    """Returns list of  tuples (customer_id, name) for every customer"""

    c.execute("SELECT * FROM Customers")
    return [(row[0], row[1]) for row in c.fetchall()]


def get_customer_by_id(customer_id):
    """Returns (customer_id, name, tier) or None """
    c.execute("SELECT Name, Default_Tier FROM Customers WHERE customer_id = ?", (customer_id,))
    result = c.fetchone()
    if result:
        return (customer_id, result[0], result[1])
    #else
    return None


def find_customer_by_name(name):
    """Returns matching row or None"""
    c.execute("SELECT customer_id, Name FROM Customers WHERE Name = ?", (name,))
    return c.fetchone()


# Pure functions that accept an explicit cursor (for FastAPI) 

def get_customer_list_pure(cursor):
    cursor.execute("SELECT customer_id, Name, Default_Tier FROM Customers")
    return cursor.fetchall()


def get_customer_by_id_pure(cursor, customer_id):
    cursor.execute("SELECT customer_id, Name, Default_Tier FROM Customers WHERE customer_id = ?", (customer_id,))
    return cursor.fetchone()


def find_customer_by_name_pure(cursor, name):
    cursor.execute("SELECT customer_id, Name, Default_Tier FROM Customers WHERE Name = ?", (name,))
    return cursor.fetchone()


def create_new_customer_pure(cursor, conn, name, phone_number, default_tier):
    cursor.execute(
        "INSERT INTO Customers (Name, Phone_Number, Default_Tier) VALUES (?, ?, ?)",
        (name, phone_number, default_tier)
    )
    customer_id = cursor.lastrowid
    return (customer_id, name, default_tier)



# CLI wrappers for testing new features in terminal

def present_CX_List():
    """prints the current cx list and returns the len of the current client list """
    customers = get_customer_list()
    print(f"{'ID':<5} | {'Name':<20} ")
    print("-" * 70)
    for customer_id, name in customers:
        print(f"{customer_id:<5} | {name:<20} ")
    print("-" * 70 + "\n")
    return len(customers)


def Current_Tier(cx_id, cx_name, default_tier):
    """traps user until a valid sequence is done to determine the new tier,either returns wholesale or retail, raises valueError on non valid inputs , handles both new and existing """

    if cx_id != 0:
        current_tier = default_tier.strip().lower()
        while True:
            x = input(f"""
                Selected Customer: {cx_name} (ID: {cx_id}) | Default Tier: {current_tier}
                Would you like to keep default price tier or change it?
                1) Keep Default
                2) Change Price Tier
                : """).strip()
            try:
                result = Current_Tier_logic(cx_id, cx_name, default_tier, x)
            except ValueError as e:
                print(f" {e}")
                continue
            print(f" {'Keeping' if x == '1' else 'Changed to'} {result[2]}")
            return result
    elif cx_id == 0:
        print(f" New customer name is: {cx_name}")
        while True:
            x = input("What tier for this customer?\n1) retail\n2) wholesale\n: ").strip()
            try:
                result = Current_Tier_logic(cx_id, cx_name, default_tier, x)
            except ValueError as e:
                print(f" {e}")
                continue
            return result


def handle_existing_customer():
    """returns a boolean for whether found or not or raises value error if not a number"""
    present_CX_List()
    while True:
        c_input = input("Choose the customer from the list above:\n: ").strip()
        try:
            customer_id = int(c_input)
            found = get_customer_by_id(customer_id)
            if found:
                print(f" Selected: {found[1]} (Tier: {found[2]})")
                return found
            else:
                print(f" {customer_id} is out of range. Try again.\n")
        except ValueError:
            print(" Please enter a valid number.\n")


def handle_new_customer():
    """if the cx not indeed new and user agrees , return ID of existing 
        else retry the cycle until success then return ID = 0 for new cx and the name and none for default tier all in a tuple"""
    while True:
        new_name = input("New customer name: ").strip().lower()
        result = find_customer_by_name(new_name)
        if result:
            cx_id = result[0]
            print(f"\n  {new_name} already exists, Customer ID in database is {cx_id}")
            x = input("1) Yes, use this customer\n2) No, enter another name\n: ").strip()
            if x == "1":
                print(" Routing back to the existing customer pipeline...")
                return cx_id
            if x != "2":
                print(" Invalid choice. please try again.\n")
        else:
            print(f"Proceeding with New Customer: {new_name}")
            return (0, new_name, None)
