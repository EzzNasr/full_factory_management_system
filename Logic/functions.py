# functions.py after refactoring to seperarate file for re use later if need be 
# we keep the file so fast API file doesn't break or we have to import every module into it 
# All real code now migrated to the modules below.


#handles all Db connections and settings retrieval 

from Logic.db             import (DB_PATH, CONFIG_PATH, TEMPLATE_PATH, INVOICES_DIR,
                               ASSETS_DIR, conn, c, load_config,
                               get_tax_config, set_tax_config, get_stock_config)

from Logic.customers      import (Current_Tier_logic,
                               Current_Tier, get_customer_list, get_customer_by_id,
                               find_customer_by_name, present_CX_List,
                               handle_existing_customer, handle_new_customer,
                               get_customer_list_pure, get_customer_by_id_pure,
                               find_customer_by_name_pure, create_new_customer_pure)

from Logic.products       import (Validate_Products, Get_Product_IDs,
                               get_product_details_pure, get_all_products_pure,
                               Validate_Products_pure, insert_new_product_pure,
                               update_product_pure, delete_product_pure)

from Logic.cart           import (Bulk_system, Individual_system, Quantity_System,
                               Bulk_system_pure, Individual_system_pure,
                               parse_discount_input)

from Logic.financials     import (Calculate_Subtotal, Apply_Discount, Apply_Taxes,
                               Calculate_Profit, Calculate_Financials_pure,
                               Package_Invoice_Data)

from Logic.invoice_output import (_encode_asset, Render_Invoice_HTML,
                               _cx_folder, _invoice_subfolder,
                               _path_to_file_uri, _html_to_pdf,
                               Save_And_Open_Invoice, Save_Client_PDF,
                               invoice_Generation)

from Logic.process        import (Phase1_Process1, Phase2_Process1, Phase3_Process1,
                               Phase4_Process1, Process1, Process2, Process2_pure,
                               Process3_logic, Process3_cancel, Process3,
                               bill_type)

