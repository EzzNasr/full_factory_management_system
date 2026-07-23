# Full Factory Management System

**A desktop-grade ERP for invoicing, stock, accounts receivable, payroll, and profit tracking — replaces per-customer Excel files with one tool.**

[![Download](https://img.shields.io/badge/Download-Windows%20.exe-blue?style=for-the-badge&logo=windows)](../../releases/latest)
![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Vite-3178C6?logo=typescript&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-DB-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-[LICENSE_PLACEHOLDER]-green)

> ⚠️ **No packaged release exists in this repo yet** — `pyinstaller`/`pystray` are already in `requirements.txt`, so a one-click `.exe` (with a tray-icon quit, like the original prototype) is clearly the intended distribution path, it's just not built yet. Until [**Releases**](../../releases/latest) has something in it, use **[Running From Source](#running-from-source)** below.

![Demo](screenshots/demo.gif)
<sub>Full flow: pick a customer → add products → set quantities → discount/tax → generate — real invoice, real management + client PDFs, seconds later.</sub>

---

## Why This Exists

A real business was running every invoice through a hand-edited Excel file per customer — no history, no stock tracking, no accounts-receivable ledger, no payroll record, no way to answer "what did we sell most this month" or "who still owes us money" without opening a dozen files. This app replaces that with one system: pick a customer, add products, get a priced, taxed, profit-calculated invoice as a PDF — and every sale, payment, return, expense, and payroll event is recorded for good, feeding a live profit dashboard.

It started as a Python CLI tool to validate the workflow with zero UI investment (`main/main.py` still exists and still works, unchanged in spirit), then grew into the full FastAPI + React app here, and further outgrew "just invoicing" into a small ERP: an accounts-receivable ledger with store credit, worker payroll with salary accrual, a business-expense ledger, and three separate profit models depending on whether you want the paper number, the cash-in-bank number, or this week's projection.

---

## Quick Start

Once a packaged release exists:

1. Download the latest `.exe` from [**Releases**](../../releases/latest).
2. Double-click it. No Python, no Node.js, no dependencies to install.
3. Your data lives locally in a SQLite file — nothing leaves your machine.
4. Unzip the release and drop your own branding into the `assets/` folder — put your signature and company logo in to replace the mocked ones. Filenames must be exactly `logo.png` and `signature.png`.
5. Quit from the tray icon in the taskbar.

Until that release exists, see **[Running From Source](#running-from-source)** — it's a two-terminal setup, not a rebuild-from-scratch.

---

## What It Does

| Feature | Screenshot |
|---|---|
| **Guided invoice wizard** — pick or create a customer, choose retail/wholesale tier, add products by ID, set quantities in bulk or individually, apply a discount (flat or %), toggle tax, review, generate | ![Invoice Wizard](screenshots/invoice-wizard.png) |
| **Mock vs. actual bills** — preview a fully priced invoice with zero database writes before you commit to a real one | ![Summary](screenshots/summary.png) |
| **Live stock-aware warnings** — selling more than you have in stock shows a warning, never blocks the sale (real businesses sell before the count updates); products can also be left fully untracked | ![Stock Management](screenshots/stock-management.png) |
| **Two invoice documents per sale** — a management copy (with profit) and a client copy where the profit row is structurally absent from the rendered HTML, not just hidden | ![Invoice Preview](screenshots/invoice-preview.png) |
| **Accounts receivable** — per-invoice and per-customer running balances, payments, refunds, store credit that auto-sweeps into new invoices, and bulk payment allocation across several open invoices at once | ![Customer Balances](screenshots/customer-balances.png) |
| **Worker payroll** — weekly base salary accrual, a bonus/deduction ledger, one-click cashouts, active/inactive workers without losing payroll history | ![Workers](screenshots/workers.png) |
| **Business expenses** — categorized expense ledger with monthly rollups, feeding directly into Net Profit | ![Expenses](screenshots/expenses.png) |
| **Dashboard with three profit models** — Gross (paper profit from completed sales), Net (real cash in minus expenses and payroll cashouts), and Estimated (this Sat–Fri week's projection) — plus top sellers, top invoices, and top customers | ![Dashboard](screenshots/dashboard.png) |
| **Order history with soft cancellation** — cancelled/returned orders are never deleted, just zeroed out of profit totals and stock-restored, so the record stays intact | ![Order Viewer](screenshots/order-viewer.png)<br>![Order Viewer 2](screenshots/order-viewer2.png) |

---

## Architecture

<p align="center">
  <img src="Docs/flowchart-overall.png" alt="Overview — Bill Type Routing" width="100%">
</p>
<p align="center"><sub><b>Overview</b> — routes every bill by type (mock, actual, returned) to the process that handles it, whether it came in through the CLI or the API.</sub></p>

<p align="center">
  <img src="Docs/flowchart-process1-4.png" alt="Phase 1-4 — Customer, Products, Quantities, Financials" width="100%">
</p>
<p align="center"><sub><b>Phases 1-4</b> — customer resolution + tier, product validation, cart building (bulk/individual), then discount → tax → profit calculation.</sub></p>

<p align="center">
  <img src="Docs/flowchart-process2.png" alt="Process 2 — Database Write & Document Generation" width="100%">
</p>
<p align="center"><sub><b>Process 2</b> — commits the sale (customer, order, line items, stock delta), then renders both invoice documents through headless Chromium.</sub></p>

<p align="center">
  <img src="Docs/flowchart-process3.png" alt="Process 3 — Returns & Cancellation" width="100%">
</p>
<p align="center"><sub><b>Process 3</b> — cancels an invoice, restores stock, zeroes its profit contribution, and renders a stamped "RETURNED" copy — without ever deleting the record.</sub></p>

<p align="center">
  <img src="Docs/flowchart-payments.png" alt="Payments — Balance, Credit, and the Three Profit Models" width="100%">
</p>
<p align="center"><sub><b>Payments ledger</b> — how balance_due, store credit sweeping, and Gross/Net/Estimated profit are each derived from the same Payments table.</sub></p>

Every piece of business logic exists in two forms: a `_pure` version that FastAPI calls (takes an explicit DB connection, raises exceptions, no blocking input), and the original CLI version it was refactored from. Neither reimplements the other — both call into the same underlying logic and share the same schema.

**[Database schema →](Docs/Database_Schema.pdf)** &nbsp;·&nbsp; **[Full pipeline breakdown, every endpoint, every formula →](TECHNICAL_BREAKDOWN.md)**

---

## Interesting Engineering Decisions

**NULL vs. zero stock.** "0 units in stock" and "we don't track this product's stock" are kept distinct — `stock_quantity` is `NULL` for untracked products and `0` for genuinely empty. Every warning, dashboard stat, and stock mutation reads this distinction (`COALESCE(stock_quantity, 0)` at every write site so an untracked product doesn't error out the first time it's sold, but also doesn't silently become "tracked" by accident), and the frontend's stock table shows untracked fields as blank, not zero.

**Soft failures over hard blocks.** Overselling triggers a warning, not a rejection — real sales sometimes get entered before stock counts catch up, and stopping an employee mid-sale over a data-entry race condition is worse than letting them proceed with eyes open.

**Client PDFs never contain profit — structurally, not visually.** The client-facing invoice is a separate server-side render (`mode="client"`) where the profit `<div>` sits behind a Jinja `{% if %}` block that's false for that render. There's no version of the client PDF where the profit figure exists anywhere in the file — the on-screen management-preview toggle is a separate, CSS-based convenience for internal use only, not how the actual client PDF is produced.

**Soft cancellation everywhere, not just on invoices.** Returned orders are never deleted — they stay in the database permanently with `Profit` zeroed out of every dashboard total, while `Total` is deliberately *preserved* so a fully-paid order that later gets cancelled correctly shows up as store credit rather than vanishing. The same pattern extends to workers: a worker with any payroll history can't be hard-deleted, only deactivated, so cashout/ledger history is never orphaned.

**Three profit numbers on purpose, not one.** Gross, Net, and Estimated profit are deliberately kept as three separate figures instead of collapsing them into "the" profit number, because they answer three different questions: what did we book (Gross), what's actually in the bank (Net — the only one that subtracts real cash-out via expenses and payroll cashouts), and what should we expect this week (Estimated, projected off active workers' salaries and this week's orders). Store-credit transfers between invoices are explicitly excluded from Net Profit's cash-in sum, since no real cash moves in a credit transfer.

**Migrating real historical invoices, not just the price catalog.** The data-migration script doesn't just import products — it ingests old per-customer Excel invoice files (Arabic column headers and all) and determines whether each one was a retail or wholesale sale by comparing recorded line values against both price tiers across the first several rows and taking whichever tier matches more often. No stored "invoice type" field existed in the old files; this recovers it after the fact.

---

## Known Limitations / Roadmap

- **No authentication.** Fine for the current single-machine/LAN desktop use case; CORS is currently wide open. Flagged for whenever a multi-user or hosted version happens.
- **No packaged release yet.** Packaging dependencies (`pyinstaller`, `pystray`) are already vendored, but the actual build + tray-icon wiring isn't done — see the note at the top of this README.
- **`requirements.txt` ships UTF-16-encoded** in this repo; convert to UTF-8 before `pip install -r` if your shell chokes on it.
- **Weekly-vs-monthly salary ambiguity.** Payroll balance accrual currently treats `Base_Salary` as a *monthly* figure (`/30 × days elapsed`), while the dashboard's Estimated Profit model treats the same field as *weekly* — the schema's own field description says "weekly." Worth reconciling before leaning on payroll balances for anything precise.
- **No automated tests for the frontend yet.** The backend has a real `pytest` suite (`tests/test_app.py`, ~65 tests) covering invoicing, payments, payroll, and all three profit models; the React app doesn't have equivalent coverage yet.
- [ROADMAP_ITEM_PLACEHOLDER — e.g. "Ship the packaged .exe + tray icon"]
- [ROADMAP_ITEM_PLACEHOLDER — e.g. "Reconcile the salary period ambiguity"]

---

## Running From Source

For anyone who wants to read, modify, or build the app themselves rather than wait on a packaged release.

**Backend**
```bash
pip install -r requirements.txt
playwright install chromium     # required once, for PDF generation
python main/main.py             # CLI mode
# — or, for the API the React app talks to —
python -m uvicorn Logic.fastapi_app:app --reload
```

**Frontend**
```bash
cd full_factory_management_system_ui
npm install    # or: pnpm install
npm run dev
```

The frontend expects the backend running on `localhost:8000` (override via `VITE_API_URL` in a `.env` file if you're tunneling instead of running locally).

Or skip both manual terminals and let the launcher do it:
```bash
python Logic/start_erp.py     # boots backend + frontend, waits for both ports, opens the browser
```
(Windows users can instead double-click `Launching/launcher.bat`.)

---

## Tech Stack

- **Backend:** Python, FastAPI, SQLite (stdlib `sqlite3`, no ORM), Jinja2, Playwright (headless Chromium for PDF generation), PyYAML, Pandas/openpyxl (Excel data migration), pytest
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4, Radix UI (shadcn/ui pattern), wouter, recharts, framer-motion
- **Packaging (in progress):** PyInstaller + pystray, targeting a standalone Windows executable with a tray-icon quit, no runtime dependencies

---

## License

[MIT]