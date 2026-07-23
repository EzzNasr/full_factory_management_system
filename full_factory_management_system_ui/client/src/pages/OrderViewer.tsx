import { useEffect, useState } from "react";
import { useParams } from "wouter";
import { FileText, Loader2, Plus, CheckCircle2, AlertCircle } from "lucide-react";
import { API_BASE as API } from "../lib/api";
import { fmtEGP } from "../lib/format";


interface OrderItem { product_id: number; name: string; qty: number; unit_price: number; line_total: number; }
interface Payment { payment_id: number; amount: number; type: string; date: string; note: string | null; }
interface OrderDetail {
  invoice_number: number; date: string; cx_name: string; tier: string;
  subtotal: number; discount: number; total: number; profit: number; status: string;
  items: OrderItem[];
}
interface PaymentData { balance_due: number; payments: Payment[]; }

const typeLabel: Record<string, string> = {
  payment: "💳 Payment",
  refund: "↩️ Refund",
  credit_applied: "🔄 Credit",
};

export default function OrderViewer() {
  const { id } = useParams();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [pmtData, setPmtData] = useState<PaymentData | null>(null);
  const [orderError, setOrderError] = useState("");

  // log payment form
  const [showForm, setShowForm] = useState(false);
  const [pmtAmount, setPmtAmount] = useState("");
  const [pmtType, setPmtType] = useState("payment");
  const [pmtNote, setPmtNote] = useState("");
  const [pmtStatus, setPmtStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [pmtError, setPmtError] = useState("");

  const fetchPayments = () =>
    fetch(`${API}/orders/${id}/payments`)
      .then(r => r.json())
      .then(setPmtData)
      .catch(() => {});

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/orders/${id}`)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setOrder)
      .catch(() => setOrderError("Could not load this order."));
    fetchPayments();
  }, [id]);

  const submitPayment = async () => {
    const raw = parseFloat(pmtAmount);
    if (isNaN(raw) || raw === 0) { setPmtError("Enter a non-zero amount."); return; }
    const amt = pmtType === "refund" ? -Math.abs(raw) : Math.abs(raw);
    setPmtStatus("loading"); setPmtError("");
    try {
      const res = await fetch(`${API}/orders/${id}/payments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount: amt, type: pmtType, note: pmtNote || null }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail); }
      setPmtStatus("success");
      setPmtAmount(""); setPmtNote(""); setPmtType("payment"); setShowForm(false);
      fetchPayments();
    } catch (e: any) { setPmtError(e.message); setPmtStatus("error"); }
  };

  if (orderError) return <p className="text-red-500 p-8">{orderError}</p>;
  if (!order) return <p className="text-muted-foreground p-8">Loading order #{id}...</p>;

  const balanceDue = pmtData?.balance_due ?? (order.status === "cancelled" ? 0 : order.total);
  const balanceColor = balanceDue > 0 ? "text-red-500" : balanceDue < 0 ? "text-blue-500" : "text-green-500";

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <FileText className="text-blue-500" /> Invoice #{order.invoice_number}
      </h1>

      {/* Order header */}
      <div className="bg-card border rounded-xl p-6 shadow-sm space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-muted-foreground">Customer:</span> <span className="font-semibold">{order.cx_name}</span></div>
          <div><span className="text-muted-foreground">Date:</span> <span className="font-semibold">{order.date}</span></div>
          <div><span className="text-muted-foreground">Tier:</span> <span className="font-semibold capitalize">{order.tier}</span></div>
          <div>
            <span className="text-muted-foreground">Status:</span>{" "}
            <span className={`font-semibold capitalize ${order.status === "cancelled" ? "text-red-500" : "text-green-600"}`}>
              {order.status}
            </span>
          </div>
        </div>

        <table className="w-full text-sm mt-2">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2">Product</th><th className="py-2">Qty</th>
              <th className="py-2 text-right">Unit</th><th className="py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((it, i) => (
              <tr key={i} className="border-b last:border-0">
                <td className="py-1.5">{it.name}</td>
                <td className="py-1.5">{it.qty}</td>
                <td className="py-1.5 text-right">{fmtEGP(it.unit_price)}</td>
                <td className="py-1.5 text-right">{fmtEGP(it.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="border-t pt-4 space-y-1 text-sm ml-auto max-w-xs">
          <div className="flex justify-between"><span>Subtotal</span><span>{fmtEGP(order.subtotal)}</span></div>
          <div className="flex justify-between"><span>Discount</span><span>-{fmtEGP(order.discount)}</span></div>
          <div className="flex justify-between font-bold text-base border-t pt-2"><span>Total</span><span>{fmtEGP(order.total)}</span></div>
          <div className="flex justify-between text-amber-600"><span>Profit</span><span>{fmtEGP(order.profit)}</span></div>
          <div className={`flex justify-between font-bold border-t pt-2 ${balanceColor}`}>
            <span>Balance Due</span><span>{fmtEGP(balanceDue)}</span>
          </div>
          {balanceDue < 0 && (
            <p className="text-xs text-blue-500 text-right">Store credit available</p>
          )}
        </div>
      </div>

      {/* Payment history */}
      <div className="bg-card border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex justify-between items-center border-b pb-2">
          <h2 className="text-lg font-semibold">Payment History</h2>
          {order.status !== "cancelled" && (
            <button
              onClick={() => { setShowForm(s => !s); setPmtStatus("idle"); setPmtError(""); }}
              className="flex items-center gap-1 text-sm bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-md font-medium"
            >
              <Plus size={14} /> Log Payment
            </button>
          )}
        </div>

        {showForm && (
          <div className="bg-background border rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Amount *</label>
                <input type="number" step="0.01" value={pmtAmount} onChange={e => setPmtAmount(e.target.value)}
                  className="w-full bg-card border rounded-md px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. 500" />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Type</label>
                <select value={pmtType} onChange={e => setPmtType(e.target.value)}
                  className="w-full bg-card border rounded-md px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="payment">Payment (cash in)</option>
                  <option value="refund">Refund (cash out, negative)</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Note (optional)</label>
              <input type="text" value={pmtNote} onChange={e => setPmtNote(e.target.value)}
                className="w-full bg-card border rounded-md px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. Cash received" />
            </div>
            {pmtError && <p className="text-red-500 text-xs">{pmtError}</p>}
            <div className="flex gap-2">
              <button onClick={submitPayment} disabled={pmtStatus === "loading"}
                className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white px-4 py-1.5 rounded-md text-sm font-semibold flex items-center gap-1">
                {pmtStatus === "loading" ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />} Save
              </button>
              <button onClick={() => setShowForm(false)}
                className="bg-muted hover:bg-muted/80 px-4 py-1.5 rounded-md text-sm font-semibold">
                Cancel
              </button>
            </div>
          </div>
        )}

        {pmtData?.payments && pmtData.payments.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b">
                <th className="py-2">Date</th><th className="py-2">Type</th>
                <th className="py-2 text-right">Amount</th><th className="py-2">Note</th>
              </tr>
            </thead>
            <tbody>
              {pmtData.payments.map(p => (
                <tr key={p.payment_id} className="border-b last:border-0">
                  <td className="py-1.5">{p.date}</td>
                  <td className="py-1.5">{typeLabel[p.type] ?? p.type}</td>
                  <td className={`py-1.5 text-right font-semibold ${p.amount < 0 ? "text-red-500" : "text-green-600"}`}>
                    {fmtEGP(p.amount)}
                  </td>
                  <td className="py-1.5 text-muted-foreground text-xs">{p.note ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-muted-foreground text-sm italic">No payments recorded.</p>
        )}
      </div>
    </div>
  );
}