import { useState } from "react";
import { FileText, CheckCircle2, AlertCircle, Loader2, RefreshCcw } from "lucide-react";
import { useInvoice } from "../contexts/InvoiceContext";
import { clearInvoiceSession } from "../contexts/InvoiceContext";
import InvoiceStepper from "../components/InvoiceStepper";
import { API_BASE } from "../lib/api";
import { fmtEGP } from "@/lib/format";

export default function Summary() {
  // 1. FIXED: We are now grabbing ALL variables from the clipboard
  const { customerId, customerName, tierChoice, quantityType, cart } = useInvoice();
  
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [invoicePaths, setInvoicePaths] = useState<{ html?: string; pdf?: string } | null>(null);

  // 2. NEW: Business Logic States
  const [billType, setBillType] = useState("mock");
  const [discount, setDiscount] = useState("");
  const [applyTax, setApplyTax] = useState(true);
  const [returnInvoiceNumber, setReturnInvoiceNumber] = useState("");
  const [amountPaidNow, setAmountPaidNow] = useState("");
  const [stockWarnings, setStockWarnings] = useState<any[]>([]);
  const [creditApplied, setCreditApplied] = useState<number>(0);

  const handleGenerate = async () => {
    setStatus("loading");
    setErrorMessage("");
    setStockWarnings([]);
    setCreditApplied(0);

    const paidNow = parseFloat(amountPaidNow);
    if (amountPaidNow && (isNaN(paidNow) || paidNow < 0)) {
      setErrorMessage("Amount paid now cannot be negative.");
      setStatus("error");
      return;
    }

    try {
      // Return path uses dedicated endpoint
      if (billType === "return") {
        const res = await fetch(`${API_BASE}/return-invoice`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ invoice_number: parseInt(returnInvoiceNumber) }),
        });
        const data = await res.json();
        if (res.ok) { setStatus("success"); setInvoicePaths({}); }
        else { setErrorMessage(JSON.stringify(data.detail)); setStatus("error"); }
        return;
      }

      const response = await fetch(`${API_BASE}/generate-invoice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: customerId,
          customer_name: customerName,
          tier_choice: tierChoice,
          order_items: cart,
          quantity_type: quantityType,
          bill_type: billType,
          discount_input: discount || "0",
          apply_tax: applyTax,
          return_invoice_number: null,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setInvoicePaths({ html: data.html_path, pdf: data.management_pdf_path });
        if (data.stock_warnings?.length) setStockWarnings(data.stock_warnings);

        // Log initial payment if amount entered and this is an actual bill
        if (billType === "actual" && paidNow > 0 && data.invoice_number && data.invoice_number !== "MOCK") {
          await fetch(`${API_BASE}/orders/${data.invoice_number}/payments`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount: paidNow, type: "payment", note: "Paid at invoice creation" }),
          });
        }

        // Automatically apply any existing store credit this customer has
        // toward the new bill, so they don't overpay on top of a credit
        // they already carried in from a prior return/overpayment.
        if (billType === "actual" && data.customer_id && data.invoice_number && data.invoice_number !== "MOCK") {
          try {
            const sweepRes = await fetch(`${API_BASE}/customers/${data.customer_id}/sweep-credit/${data.invoice_number}`, {
              method: "POST",
            });
            const sweepData = await sweepRes.json();
            if (sweepRes.ok && sweepData.applied > 0) {
              setCreditApplied(sweepData.applied);
            }
          } catch { /* non-fatal — credit can still be applied manually later */ }
        }

        setStatus("success");
        if (billType === "actual") clearInvoiceSession();
      } else {
        setErrorMessage(JSON.stringify(data.detail));
        setStatus("error");
      }
    } catch (error) {
      setErrorMessage("Network Error: Is the FastAPI server running?");
      setStatus("error");
    }
  };

  return (
    <>
      <InvoiceStepper />
      <div className="max-w-5xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <FileText className="text-blue-500" /> Final Summary & Generation
        </h1>
        <p className="text-muted-foreground mt-2">Configure taxes, discounts, and bill type before finalizing.</p>
      </div>

      <div className="grid gap-6 grid-cols-1 lg:grid-cols-3">
        {/* Left Column: Data Review & Configurations */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Bill Type Selector */}
          <div className="bg-card border rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold mb-4 border-b pb-2">1. Select Process Type</h2>
            <select 
              value={billType}
              onChange={(e) => setBillType(e.target.value)}
              className="w-full bg-background border rounded-md px-4 py-3 font-medium focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="mock">🟡 Mock Bill (Preview only, no database changes)</option>
              <option value="actual">🟢 Actual Bill (Save to DB, issue real Invoice #)</option>
              <option value="return">🔴 Return / Cancel Bill (Reverse an existing invoice)</option>
            </select>
          </div>

          {/* Dynamic Content based on Bill Type */}
          {billType === "return" ? (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-red-600 mb-4 flex items-center gap-2">
                <RefreshCcw size={20} /> Process Return
              </h2>
              <label className="block text-sm font-medium mb-2 text-foreground">Invoice Number to Return:</label>
              <input 
                type="number" 
                value={returnInvoiceNumber}
                onChange={(e) => setReturnInvoiceNumber(e.target.value)}
                placeholder="e.g. 104"
                className="w-full bg-background border rounded-md px-4 py-2 outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>
          ) : (
            <>
              <div className="bg-card border rounded-xl p-6 shadow-sm grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-semibold mb-2">Apply Discount</label>
                  <input 
                    type="text" 
                    value={discount}
                    onChange={(e) => setDiscount(e.target.value)}
                    placeholder="e.g. '10%' or '50'"
                    className="w-full bg-background border rounded-md px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-muted-foreground mt-1">Use % for percentage, or type a flat amount.</p>
                </div>
                
                <div>
                  <label className="block text-sm font-semibold mb-2">System Taxes</label>
                  <div className="flex items-center mt-3">
                    <input 
                      type="checkbox" 
                      id="taxToggle"
                      checked={applyTax}
                      onChange={(e) => setApplyTax(e.target.checked)}
                      className="w-5 h-5 rounded text-blue-600 focus:ring-blue-500 bg-background border-gray-600"
                    />
                    <label htmlFor="taxToggle" className="ml-3 text-sm font-medium">
                      Apply Tax (Reads from config.yaml)
                    </label>
                  </div>
                </div>

                {billType === "actual" && (
                  <div className="col-span-2">
                    <label className="block text-sm font-semibold mb-2">Amount Paid Now (optional)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={amountPaidNow}
                      onChange={e => setAmountPaidNow(e.target.value)}
                      placeholder="e.g. 500 — logs a payment row at creation"
                      className="w-full bg-background border rounded-md px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-muted-foreground mt-1">Leave blank if nothing was collected now.</p>
                  </div>
                )}
              </div>

              {/* Order Review */}
              <div className="bg-card border rounded-xl p-6 shadow-sm">
                <h2 className="text-lg font-semibold mb-4 border-b pb-2">Order Summary</h2>
                <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                  <div><span className="text-muted-foreground">Customer:</span> <span className="font-semibold">{customerName || "N/A"}</span></div>
                  <div><span className="text-muted-foreground">Tier:</span> <span className="font-semibold capitalize">{tierChoice}</span></div>
                  <div><span className="text-muted-foreground">Quantity Mode:</span> <span className="font-semibold capitalize">{quantityType}</span></div>
                </div>
                
                <div className="bg-background border rounded-md p-3 max-h-40 overflow-y-auto">
                  {cart.length > 0 ? cart.map((item, idx) => (
                    <div key={idx} className="flex justify-between py-1 border-b last:border-0 text-sm">
                      <span>Product ID: {item.product_id}</span>
                      <span className="font-semibold">Qty: {item.quantity}</span>
                    </div>
                  )) : <p className="text-muted-foreground text-sm italic">Cart is empty.</p>}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Column: Action Panel */}
        <div className="space-y-6">
          <div className="bg-card border rounded-xl shadow-sm p-6 flex flex-col items-center text-center">
            <h3 className="font-semibold text-lg mb-2">Ready to Fire Engine</h3>
            <p className="text-sm text-muted-foreground mb-6">
              {billType === "mock" ? "Will generate files without altering the database." : 
               billType === "actual" ? "Will commit to database and generate final files." : 
               "Will reverse the invoice and restore stock."}
            </p>

            <button
              onClick={handleGenerate}
              disabled={status === "loading" || (billType !== "return" && cart.length === 0)}
              className={`w-full text-white font-bold py-3 px-6 rounded-md shadow-lg transition-transform active:scale-95 flex justify-center items-center gap-2 ${
                billType === "return" ? "bg-red-600 hover:bg-red-500" : "bg-blue-600 hover:bg-blue-500"
              } disabled:opacity-50 disabled:pointer-events-none`}
            >
              {status === "loading" ? <><Loader2 className="animate-spin" size={20} /> Processing...</> : 
               billType === "return" ? "Process Return" : "Generate Invoice"}
            </button>
          </div>

          {/* Feedback Alerts */}
          {status === "error" && (
            <div className="bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg p-4 flex gap-3">
              <AlertCircle className="flex-shrink-0 mt-0.5" size={20} />
              <div className="text-sm"><p className="font-bold">Error</p><p>{errorMessage}</p></div>
            </div>
          )}

          {status === "success" && (
            <div className="space-y-3">
              <div className="bg-green-500/10 text-green-500 border border-green-500/20 rounded-lg p-4 flex gap-3">
                <CheckCircle2 className="flex-shrink-0 mt-0.5" size={20} />
                <div className="text-sm">
                  <p className="font-bold">{billType === "return" ? "Invoice Cancelled." : "Success!"}</p>
                  {invoicePaths?.html && <p className="break-all mt-1 opacity-90">{invoicePaths.html}</p>}
                  {creditApplied > 0 && (
                    <p className="mt-1 font-semibold">Applied {fmtEGP(creditApplied)} of existing store credit to this bill.</p>
                  )}
                </div>
              </div>
              {stockWarnings.length > 0 && (
                <div className="bg-amber-500/10 text-amber-600 border border-amber-500/20 rounded-lg p-4 text-sm">
                  <p className="font-bold mb-1">⚠️ Stock Warnings</p>
                  {stockWarnings.map((w: any, i: number) => (
                    <p key={i}>{w.item_name} (ID {w.product_id}): stock now {w.stock_quantity}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}