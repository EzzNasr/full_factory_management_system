import os
import re
import base64
import webbrowser
from jinja2 import Template

from .db import TEMPLATE_PATH, INVOICES_DIR, ASSETS_DIR, get_tax_config


#  Asset helpers

def _encode_asset(filename):
    """Returns a Base64 data URI for an asset file. Returns '' if missing."""
    # Embedding the logo/signature as a data URI means the generated HTML
    # (and the PDF made from it) doesn't depend on the asset file still
    # being there later - everything needed to render is baked into the file.
    path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(path):
        return ""
    ext  = os.path.splitext(filename)[1].lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png",  "svg":  "image/svg+xml"}.get(ext, "image/png")
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


#  Path helpers

def _cx_folder(cx_name):
    """Returns .../invoices/<cx_name>/, creating it if needed."""
    # Customer names can contain characters that aren't safe in folder
    # names (slashes, colons, etc.), so we swap anything sketchy out for
    # an underscore before touching the filesystem.
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", cx_name).strip()
    folder    = os.path.join(INVOICES_DIR, safe_name)
    os.makedirs(folder, exist_ok=True)
    return folder


def _invoice_subfolder(cx_name, invoice_slug):
    """Returns .../invoices/<cx_name>/<invoice_slug>/, creating it if needed."""
    # Each invoice gets its own folder inside the customer's folder so the
    # html/pdf pair for one invoice never mixes with another invoice's files.
    sub = os.path.join(_cx_folder(cx_name), invoice_slug)
    os.makedirs(sub, exist_ok=True)
    return sub


def _path_to_file_uri(path):
    """Converts an absolute OS path to a valid file:/// URI (Windows + POSIX)."""
    # pathname2url handles the OS-specific slash/escaping differences so this
    # works whether we're running on Windows or Linux/Mac without branching
    # on platform ourselves.
    import urllib.request
    return "file:///" + urllib.request.pathname2url(os.path.abspath(path)).lstrip("/")


#  PDF engine (Playwright headless Chromium)

def _html_to_pdf(html_path, pdf_path):
    # We render through an actual browser engine instead of a lightweight
    # HTML-to-PDF library so that the PDF looks exactly like what shows up
    # in the browser preview - same CSS, same fonts, no surprises.
    from playwright.sync_api import sync_playwright
    import threading

    file_uri = _path_to_file_uri(html_path)

    def run_sync_playwright():
        # Playwright's sync API can't run on certain event loops (like the
        # one some frameworks or notebooks already have going), so we run
        # it inside its own dedicated thread to sidestep that entirely.
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page    = browser.new_page()
            page.goto(file_uri, wait_until="networkidle")
            page.pdf(
                path             = pdf_path,
                format           = "A4",
                margin           = {"top": "10mm", "bottom": "10mm",
                                    "left": "10mm",  "right": "10mm"},
                print_background = True,
            )
            browser.close()

    thread = threading.Thread(target=run_sync_playwright)
    thread.start()
    thread.join()


#  Core rendering

def Render_Invoice_HTML(invoice_packet, invoice_number, invoice_date,
                        business_name="NAVY LLC", mode="management"):
    """Pure function — returns a rendered HTML string, no disk I/O."""
    # Kept as a pure function on purpose - no file writes here - so it can
    # be reused for both the management copy and (indirectly) tested or
    # previewed without touching disk.
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = Template(f.read())

    table_rows = [
        {"id": row[0], "qty": row[1], "unit_price": row[2], "line_total": row[3], "name": row[4]}
        for row in invoice_packet["table_data"]
    ]
    # The financials dict stores discount/tax with their sign baked in
    # (e.g. "-50.00" / "+12.00") for display elsewhere, but here we just
    # want the plain magnitude to hand to the template.
    discount_str = invoice_packet["financials"]["discount"].lstrip("-")
    tax_str      = invoice_packet["financials"]["tax"].lstrip("+")
    apply_tax, tax_rate = get_tax_config()
    amount_paid  = invoice_packet["financials"].get("amount_paid")
    balance_due  = invoice_packet["financials"].get("balance_due")

    return template.render(
        business_name  = business_name,
        invoice_number = invoice_number,
        invoice_date   = invoice_date,
        customer_name  = invoice_packet["header"]["customer_name"],
        tier           = invoice_packet["header"]["tier"],
        mode           = mode,
        allow_toggle   = True,
        table_rows     = table_rows,
        subtotal       = invoice_packet["financials"]["subtotal"],
        discount_pct   = invoice_packet["financials"]["discount_pct"],
        discount_amount= invoice_packet["financials"]["discount_amount"],
        after_discount = invoice_packet["financials"]["after_discount"],
        discount       = discount_str,
        tax            = tax_str,
        grand_total    = invoice_packet["financials"]["grand_total"],
        profit         = invoice_packet["system_metrics"]["internal_profit"],
        tax_enabled    = apply_tax,
        tax_rate_pct   = int(round(tax_rate * 100)),
        amount_paid    = amount_paid,
        balance_due    = balance_due,
        logo_uri       = _encode_asset("logo.png"),
        signature_uri  = _encode_asset("signature.png"),
    )


#  File saving

def Save_And_Open_Invoice(html, invoice_slug, cx_name=None, output_dir=None):
    """
    Saves management HTML + management PDF.
    Layout:  invoices/<cx_name>/<invoice_slug>/<invoice_slug>.html / .pdf
    Returns: (html_path, mgmt_pdf_path)
    """
    # output_dir lets a caller override where things get saved; otherwise
    # we fall back to the normal <customer>/<invoice> folder structure, and
    # if we don't even have a customer name we just dump it at the top
    # level of the invoices folder rather than failing outright.
    if output_dir:
        full_output_dir = output_dir
        os.makedirs(full_output_dir, exist_ok=True)
    elif cx_name:
        full_output_dir = _invoice_subfolder(cx_name, invoice_slug)
    else:
        full_output_dir = INVOICES_DIR
        os.makedirs(full_output_dir, exist_ok=True)

    html_path = os.path.join(full_output_dir, f"{invoice_slug}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # The HTML file is always saved even if PDF generation fails below, so
    # nobody loses the invoice entirely just because Playwright/Chromium
    # had a bad time.
    mgmt_pdf_path = os.path.join(full_output_dir, f"{invoice_slug}.pdf")
    try:
        _html_to_pdf(html_path, mgmt_pdf_path)
        print(f"  Management PDF  -> {mgmt_pdf_path}")
    except Exception as e:
        print(f"  Management PDF generation failed: {e}")
        mgmt_pdf_path = None

    webbrowser.open(_path_to_file_uri(html_path))
    return html_path, mgmt_pdf_path


def Save_Client_PDF(invoice_packet, invoice_slug, invoice_number, invoice_date,
                    cx_name, business_name="NAVY LLC", output_dir=None):
    """
    Renders a CLIENT copy (mode='client', no profit) and saves it as PDF.
    Layout:  invoices/<cx_name>/<invoice_slug>/<invoice_slug>--CLIENT.pdf
    """
    # This duplicates most of Render_Invoice_HTML on purpose: the client
    # version needs profit hidden and the tier-toggle UI disabled, so
    # rather than bolt more branching onto the shared renderer we just
    # render a second, separate copy here with those two things different.
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = Template(f.read())

    table_rows = [
        {"id": row[0], "qty": row[1], "unit_price": row[2], "line_total": row[3], "name": row[4]}
        for row in invoice_packet["table_data"]
    ]
    discount_str = invoice_packet["financials"]["discount"].lstrip("-")
    tax_str      = invoice_packet["financials"]["tax"].lstrip("+")
    apply_tax, tax_rate = get_tax_config()
    amount_paid  = invoice_packet["financials"].get("amount_paid")
    balance_due  = invoice_packet["financials"].get("balance_due")

    client_html = template.render(
        business_name  = business_name,
        invoice_number = invoice_number,
        invoice_date   = invoice_date,
        customer_name  = invoice_packet["header"]["customer_name"],
        tier           = invoice_packet["header"]["tier"],
        mode           = "client",
        allow_toggle   = False,
        table_rows     = table_rows,
        subtotal       = invoice_packet["financials"]["subtotal"],
        discount_pct   = invoice_packet["financials"]["discount_pct"],
        discount_amount= invoice_packet["financials"]["discount_amount"],
        after_discount = invoice_packet["financials"]["after_discount"],
        discount       = discount_str,
        tax            = tax_str,
        grand_total    = invoice_packet["financials"]["grand_total"],
        profit         = "—",
        tax_enabled    = apply_tax,
        tax_rate_pct   = int(round(tax_rate * 100)),
        amount_paid    = amount_paid,
        balance_due    = balance_due,
        logo_uri       = _encode_asset("logo.png"),
        signature_uri  = _encode_asset("signature.png"),
    )

    if output_dir:
        full_output_dir = output_dir
    elif cx_name:
        full_output_dir = _invoice_subfolder(cx_name, invoice_slug)
    else:
        full_output_dir = INVOICES_DIR
    os.makedirs(full_output_dir, exist_ok=True)

    # We only ever want the finished PDF on disk, not the intermediate
    # HTML used to build it, so the html here is written to a "_tmp" file
    # and deleted once the PDF conversion is done (see finally block below).
    tmp_html_path   = os.path.join(full_output_dir, f"{invoice_slug}--CLIENT_tmp.html")
    client_pdf_path = os.path.join(full_output_dir, f"{invoice_slug}--CLIENT.pdf")

    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(client_html)

    try:
        _html_to_pdf(tmp_html_path, client_pdf_path)
        print(f"  Client PDF      -> {client_pdf_path}")
    except Exception as e:
        print(f"  Client PDF generation failed: {e}")
        client_pdf_path = None
    finally:
        # Clean up the temp HTML regardless of whether PDF conversion
        # succeeded or blew up, so we never leave stray tmp files behind.
        if os.path.exists(tmp_html_path):
            os.remove(tmp_html_path)

    return client_pdf_path


def invoice_Generation(invoice_packet, invoice_slug, invoice_date,
                       cx_name=None, business_name="NAVY LLC", mode="management"):
    """Orchestrates: render → save HTML + mgmt PDF → client PDF → open browser."""
    # invoice_slug looks like "invoice#123--somecustomer", and we only want
    # the "123" part to show on the actual invoice, so we pull it out here
    # instead of passing the whole slug through as the displayed number.
    match = re.search(r'invoice#(.+?)(?:--|$)', invoice_slug)
    invoice_number_display = match.group(1) if match else invoice_slug

    html = Render_Invoice_HTML(invoice_packet, invoice_number_display, invoice_date, business_name, mode)
    html_path, mgmt_pdf = Save_And_Open_Invoice(html, invoice_slug, cx_name=cx_name)
    client_pdf = Save_Client_PDF(
        invoice_packet, invoice_slug, invoice_number_display, invoice_date,
        cx_name=cx_name, business_name=business_name,
    )
    print(f"Invoice saved and opened: {html_path}")
    return html_path, mgmt_pdf, client_pdf