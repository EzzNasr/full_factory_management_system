import { useEffect, useState } from "react";
import { Wallet, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { API_BASE as API } from "../lib/api";
import { fmtEGP } from "../lib/format"


interface Customer { customer_id: number; name: string; default_tier: string; }
interface InvoiceBalance {
  invoice_number: number; date: string; total: number;
  status: string; balance_due: number;
}

export default function CustomerBalances() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [balances, setBalances] = useState<InvoiceBalance[]>([]);
  const [loadingBalances, setLoadingBalances] = useState(false);

  // allocation state
  const [allocations, setAllocations] = useState<Record<number, string>>({});
  const [cashEntered, setCashEntered] = useState("");
  const [submitStatus, setSubmitStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [submitMsg, setSubmitMsg] = useState("");

  // per-credit-invoice action state (refund vs. apply-to-another-bill)
  const [creditAction, setCreditAction] = useState<Record<number, { mode: "refund" | "apply"; amount: string; targetInvoice: string }>>({});
  const [creditActionStatus, setCreditActionStatus] = useState<Record<number, "idle" | "loading" | "error" | "success">>({});
  const [creditActionMsg, setCreditActionMsg] = useState<Record<number, string>>({});

  useEffect(() => {
    fetch(`${API}/customers`).then(r => r.json()).then(setCustomers).catch(() => {});
  }, []);

  const loadBalances = (id: number) => {
    if (!id || isNaN(id)) {
      setSelectedId(null);
      setBalances([]);
      setAllocations({});
      setCashEntered("");
      setSubmitStatus("idle");
      return;
    }
    setSelectedId(id);
    setLoadingBalances(true);
    setAllocations({});
    setCashEntered("");
    setSubmitStatus("idle");
    fetch(`${API}/customers/${id}/balances`)
      .then(async r => {
        if (!r.ok) throw new Error("Could not load balances");
        return r.json();
      })
      .then(data => { setBalances(Array.isArray(data) ? data : []); setLoadingBalances(false); })
      .catch(() => { setBalances([]); setLoadingBalances(false); });
  };

  const openCreditAction = (invoiceNumber: number, mode: "refund" | "apply", maxAmount: number) => {
    setCreditAction(prev => ({
      ...prev,
      [invoiceNumber]: prev[invoiceNumber]?.mode === mode
        ? { ...prev[invoiceNumber], mode: "" as any } // toggle closed if clicked again
        : { mode, amount: fmtEGP(maxAmount), targetInvoice: "" },
    }));
    setCreditActionStatus(prev => ({ ...prev, [invoiceNumber]: "idle" }));
    setCreditActionMsg(prev => ({ ...prev, [invoiceNumber]: "" }));
  };

  const submitRefund = async (invoiceNumber: number) => {
    const action = creditAction[invoiceNumber];
    const amt = parseFloat(action?.amount || "0");
    if (isNaN(amt) || amt <= 0) {
      setCreditActionStatus(prev => ({ ...prev, [invoiceNumber]: "error" }));
      setCreditActionMsg(prev => ({ ...prev, [invoiceNumber]: "Enter a positive amount." }));
      return;
    }
    setCreditActionStatus(prev => ({ ...prev, [invoiceNumber]: "loading" }));
    try {
      const res = await fetch(`${API}/orders/${invoiceNumber}/payments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount: -Math.abs(amt), type: "refund", note: "Refunded from store credit" }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "Refund failed");
      setCreditActionStatus(prev => ({ ...prev, [invoiceNumber]: "success" }));
      setCreditActionMsg(prev => ({ ...prev, [invoiceNumber]: `Refunded ${fmtEGP(amt)}. This reduces Net Profit.` }));
      setCreditAction(prev => ({ ...prev, [invoiceNumber]: { ...prev[invoiceNumber], mode: "" as any } }));
      loadBalances(selectedId!);
    } catch (e: any) {
      setCreditActionStatus(prev => ({ ...prev, [invoiceNumber]: "error" }));
      setCreditActionMsg(prev => ({ ...prev, [invoiceNumber]: e.message }));
    }
  };

  const submitApplyToBill = async (sourceInvoice: number) => {
    const action = creditAction[sourceInvoice];
    const amt = parseFloat(action?.amount || "0");
    const target = parseInt(action?.targetInvoice || "");
    if (isNaN(amt) || amt <= 0) {
      setCreditActionStatus(prev => ({ ...prev, [sourceInvoice]: "error" }));
      setCreditActionMsg(prev => ({ ...prev, [sourceInvoice]: "Enter a positive amount." }));
      return;
    }
    if (!target) {
      setCreditActionStatus(prev => ({ ...prev, [sourceInvoice]: "error" }));
      setCreditActionMsg(prev => ({ ...prev, [sourceInvoice]: "Choose an invoice to apply this credit to." }));
      return;
    }
    setCreditActionStatus(prev => ({ ...prev, [sourceInvoice]: "loading" }));
    try {
      const res = await fetch(`${API}/orders/credit-apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_invoice: sourceInvoice, target_invoice: target, amount: amt }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "Apply failed");
      setCreditActionStatus(prev => ({ ...prev, [sourceInvoice]: "success" }));
      setCreditActionMsg(prev => ({ ...prev, [sourceInvoice]: `Applied ${fmtEGP(amt)} to Invoice #${target}. No cash moved, does not affect Net Profit.` }));
      setCreditAction(prev => ({ ...prev, [sourceInvoice]: { ...prev[sourceInvoice], mode: "" as any } }));
      loadBalances(selectedId!);
    } catch (e: any) {
      setCreditActionStatus(prev => ({ ...prev, [sourceInvoice]: "error" }));
      setCreditActionMsg(prev => ({ ...prev, [sourceInvoice]: e.message }));
    }
  };
  const openInvoices = balances.filter(b => b.balance_due > 0 && b.status !== "cancelled");
  const creditInvoices = balances.filter(b => b.balance_due < 0);
  const totalCredit = creditInvoices.reduce((sum, b) => sum + Math.abs(b.balance_due), 0);
  const totalCash = parseFloat(cashEntered) || 0;
  const totalAllocated = Object.values(allocations).reduce((s, v) => s + (parseFloat(v) || 0), 0);
  const remaining = parseFloat(fmtEGP(totalCash - totalAllocated));

  const autoFill = () => {
    let left = totalCash;
    const newAlloc: Record<number, string> = {};
    for (const inv of openInvoices) {
      if (left <= 0) break;
      const pay = Math.min(left, inv.balance_due);
      newAlloc[inv.invoice_number] = fmtEGP(pay);
      left = parseFloat(fmtEGP(left - pay));
    }
    setAllocations(newAlloc);
  };

  const submit = async () => {
    const entries = Object.entries(allocations)
      .map(([inv, amt]) => ({ invoice_number: parseInt(inv), amount: parseFloat(amt) }))
      .filter(e => e.amount > 0);
    if (entries.length === 0) { setSubmitMsg("No amounts entered."); setSubmitStatus("error"); return; }
    if (totalAllocated > totalCash + 0.001) { setSubmitMsg("Allocated exceeds cash entered."); setSubmitStatus("error"); return; }

    setSubmitStatus("loading"); setSubmitMsg("");
    try {
      const res = await fetch(`${API}/customers/${selectedId}/payments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allocations: entries }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail);
      setSubmitStatus("success"); setSubmitMsg(d.message);
      loadBalances(selectedId!);
    } catch (e: any) { setSubmitStatus("error"); setSubmitMsg(e.message); }
  };

  const balanceColor = (b: number) => b > 0 ? "text-red-500" : b < 0 ? "text-blue-500" : "text-green-600";

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <Wallet className="text-blue-500" /> Customer Balances
      </h1>

      {/* Customer selector */}
      <div className="bg-card border rounded-xl p-6 shadow-sm">
        <label className="block text-sm font-medium mb-2 text-muted-foreground">Select Customer</label>
        <select
          className="w-full bg-background border rounded-md px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          value={selectedId ?? ""}
          onChange={e => loadBalances(parseInt(e.target.value))}
        >
          <option value="">— Choose a customer —</option>
          {customers.map(c => (
            <option key={c.customer_id} value={c.customer_id}>
              [{c.customer_id}] {c.name}
            </option>
          ))}
        </select>
      </div>

      {loadingBalances && <p className="text-muted-foreground">Loading...</p>}

      {selectedId && !loadingBalances && (
        <>
          {/* Balance overview table */}
          <div className="bg-card border rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b bg-background/50">
                  <th className="py-3 px-4">Invoice</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4 text-right">Total</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Balance Due</th>
                </tr>
              </thead>
              <tbody>
                {balances.map(b => (
                  <tr key={b.invoice_number} className="border-b last:border-0">
                    <td className="py-2 px-4 font-semibold">#{b.invoice_number}</td>
                    <td className="py-2 px-4 text-muted-foreground">{b.date}</td>
                    <td className="py-2 px-4 text-right">{fmtEGP(b.total)}</td>
                    <td className="py-2 px-4 capitalize">
                      <span className={b.status === "cancelled" ? "text-red-500" : ""}>{b.status}</span>
                    </td>
                    <td className={`py-2 px-4 text-right font-bold ${balanceColor(b.balance_due)}`}>
                      {fmtEGP(b.balance_due)}
                      {b.balance_due < 0 && <span className="text-xs font-normal ml-1">(credit)</span>}
                    </td>
                  </tr>
                ))}
                {balances.length === 0 && (
                  <tr><td colSpan={5} className="py-6 text-center text-muted-foreground italic">No orders.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {creditInvoices.length > 0 && (
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-6 shadow-sm space-y-3">
              <h2 className="text-lg font-semibold text-blue-600">
                Store Credit Available: {fmtEGP(totalCredit)}
              </h2>
              <p className="text-xs text-muted-foreground">
                From overpaid or refunded invoices. Use "Apply Credit" on the invoice you want to pay down —
                new bills for this customer will also automatically pull from this credit at checkout.
              </p>
              {creditInvoices.map(inv => {
                const available = Math.abs(inv.balance_due);
                const action = creditAction[inv.invoice_number];
                const status = creditActionStatus[inv.invoice_number] || "idle";
                const msg = creditActionMsg[inv.invoice_number] || "";
                return (
                  <div key={inv.invoice_number} className="bg-background border rounded-md p-3 text-sm space-y-2">
                    <div className="flex justify-between items-center">
                      <span>Invoice #{inv.invoice_number} ({inv.date})</span>
                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-blue-600">{fmtEGP(available)} credit</span>
                        <button
                          onClick={() => openCreditAction(inv.invoice_number, "refund", available)}
                          className="text-xs bg-red-600 hover:bg-red-500 text-white px-2 py-1 rounded"
                        >
                          Refund
                        </button>
                        <button
                          onClick={() => openCreditAction(inv.invoice_number, "apply", available)}
                          className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded"
                        >
                          Apply to Bill
                        </button>
                      </div>
                    </div>

                    {action?.mode === "refund" && (
                      <div className="flex gap-2 items-center pt-2 border-t">
                        <input
                          type="number" step="0.01" max={available}
                          value={action.amount}
                          onChange={e => setCreditAction(prev => ({ ...prev, [inv.invoice_number]: { ...prev[inv.invoice_number], amount: e.target.value } }))}
                          className="w-28 bg-card border rounded-md px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-red-500"
                        />
                        <span className="text-xs text-muted-foreground">of {fmtEGP(available)} — real cash out, reduces Net Profit</span>
                        <button onClick={() => submitRefund(inv.invoice_number)} disabled={status === "loading"}
                          className="ml-auto text-xs bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white px-3 py-1.5 rounded font-semibold">
                          Confirm Refund
                        </button>
                      </div>
                    )}

                    {action?.mode === "apply" && (
                      <div className="flex flex-wrap gap-2 items-center pt-2 border-t">
                        <input
                          type="number" step="0.01" max={available}
                          value={action.amount}
                          onChange={e => setCreditAction(prev => ({ ...prev, [inv.invoice_number]: { ...prev[inv.invoice_number], amount: e.target.value } }))}
                          className="w-28 bg-card border rounded-md px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <select
                          value={action.targetInvoice}
                          onChange={e => setCreditAction(prev => ({ ...prev, [inv.invoice_number]: { ...prev[inv.invoice_number], targetInvoice: e.target.value } }))}
                          className="bg-card border rounded-md px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="">-- apply to which invoice? --</option>
                          {openInvoices.filter(o => o.invoice_number !== inv.invoice_number).map(o => (
                            <option key={o.invoice_number} value={o.invoice_number}>
                              #{o.invoice_number} (owes {fmtEGP(o.balance_due)})
                            </option>
                          ))}
                        </select>
                        <button onClick={() => submitApplyToBill(inv.invoice_number)} disabled={status === "loading"}
                          className="ml-auto text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3 py-1.5 rounded font-semibold">
                          Confirm Transfer
                        </button>
                      </div>
                    )}

                    {msg && (
                      <p className={`text-xs ${status === "error" ? "text-red-500" : "text-green-600"}`}>{msg}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Payment allocation */}
          {openInvoices.length > 0 && (
            <div className="bg-card border rounded-xl p-6 shadow-sm space-y-4">
              <h2 className="text-lg font-semibold border-b pb-2">Allocate Incoming Cash</h2>

              <div className="flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-xs text-muted-foreground mb-1">Cash Received</label>
                  <input
                    type="number" step="0.01" value={cashEntered}
                    onChange={e => setCashEntered(e.target.value)}
                    className="w-full bg-background border rounded-md px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Total cash in hand"
                  />
                </div>
                <button
                  onClick={autoFill}
                  disabled={!totalCash}
                  className="bg-muted hover:bg-muted/80 disabled:opacity-50 px-4 py-2 rounded-md text-sm font-semibold"
                >
                  Auto-fill (oldest first)
                </button>
              </div>

              <div className="space-y-2">
                {openInvoices.map(inv => (
                  <div key={inv.invoice_number} className="flex items-center gap-3 bg-background border rounded-md p-3">
                    <div className="flex-1">
                      <span className="font-semibold text-sm">Invoice #{inv.invoice_number}</span>
                      <span className="text-muted-foreground text-xs ml-2">{inv.date}</span>
                      <span className="text-red-500 text-xs ml-2">Owes: {fmtEGP(inv.balance_due)}</span>
                    </div>
                    <input
                      type="number" step="0.01"
                      value={allocations[inv.invoice_number] ?? ""}
                      onChange={e => setAllocations(a => ({ ...a, [inv.invoice_number]: e.target.value }))}
                      className="w-28 bg-card border rounded-md px-3 py-1.5 text-sm text-right outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="0.00"
                    />
                  </div>
                ))}
              </div>

              <div className="flex justify-between text-sm pt-2 border-t">
                <span className="text-muted-foreground">Allocated / Cash Entered</span>
                <span className={`font-semibold ${remaining < 0 ? "text-red-500" : ""}`}>
                  {fmtEGP(totalAllocated)} / {fmtEGP(totalCash)}
                  {remaining > 0 && <span className="text-muted-foreground ml-2">({fmtEGP(remaining)} unallocated)</span>}
                </span>
              </div>

              {submitStatus === "error" && (
                <div className="flex gap-2 text-red-500 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <AlertCircle size={16} className="shrink-0 mt-0.5" /> {submitMsg}
                </div>
              )}
              {submitStatus === "success" && (
                <div className="flex gap-2 text-green-600 text-sm bg-green-500/10 border border-green-500/20 rounded-lg p-3">
                  <CheckCircle2 size={16} className="shrink-0 mt-0.5" /> {submitMsg}
                </div>
              )}

              <button
                onClick={submit}
                disabled={submitStatus === "loading" || totalAllocated === 0}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold py-2.5 rounded-md flex justify-center items-center gap-2"
              >
                {submitStatus === "loading" ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                Confirm Payments
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}