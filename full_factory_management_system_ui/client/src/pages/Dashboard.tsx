import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";
import { TrendingUp, Award, Users, ChevronRight, X, Loader2 } from "lucide-react";
import { API_BASE as API } from "../lib/api";

interface Stats {
  top_items: { name: string; qty: number }[];
  top_bills: { invoice_number: number; cx_name: string; profit: number }[];
  top_customers: { name: string; profit: number }[];
  gross_profit: number;
  net_profit: number;
  estimated_profit: number;
  estimated_period_start: string;
  estimated_period_end: string;
}

interface Breakdown {
  type: "gross" | "net" | "estimated";
  data: any;
}

function profitColor(val: number) {
  return val >= 0 ? "text-amber-600" : "text-red-500";
}

// FIX: single formatter used everywhere — comma separator + 2 decimals
const fmtEGP = (val: number) =>
  "EGP " + (val ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function BreakdownPanel({ breakdown, onClose }: { breakdown: Breakdown; onClose: () => void }) {
  const { type, data } = breakdown;

  const Row = ({ label, amount, muted }: { label: string; amount: number; muted?: boolean }) => (
    <div className={`flex justify-between py-1.5 border-b last:border-0 text-sm ${muted ? "text-muted-foreground" : ""}`}>
      <span className="truncate pr-4">{label}</span>
      <span className={`font-semibold shrink-0 ${amount < 0 ? "text-red-500" : ""}`}>{fmtEGP(amount)}</span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div className="w-full max-w-lg bg-background border-l shadow-xl overflow-y-auto p-6 space-y-6"
           onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold capitalize">{type} Profit — Breakdown</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        {type === "gross" && (
          <>
            <p className="text-2xl font-bold text-amber-600">{fmtEGP(data.total ?? 0)}</p>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Orders</h3>
              {(data.items || []).map((it: any, i: number) => (
                <Row key={i} label={`#${it.invoice_number} — ${it.cx_name} (${it.date})`} amount={it.profit} />
              ))}
              {(data.items || []).length === 0 && <p className="text-muted-foreground text-sm italic">No orders.</p>}
            </div>
          </>
        )}

        {type === "net" && (
          <>
            <p className={`text-2xl font-bold ${profitColor(data.total ?? 0)}`}>{fmtEGP(data.total ?? 0)}</p>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Payments Received (+{fmtEGP(data.cash_in ?? 0)})</h3>
              {(data.payment_items || []).filter((p: any) => p.amount > 0).map((p: any, i: number) => (
                <Row key={i} label={`Invoice #${p.invoice_number} — ${p.type} ${p.date}`} amount={p.amount} />
              ))}
              {(data.payment_items || []).filter((p: any) => p.amount < 0).map((p: any, i: number) => (
                <Row key={i} label={`Invoice #${p.invoice_number} — ${p.type} ${p.date}`} amount={p.amount} />
              ))}
            </div>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Expenses (-{fmtEGP(data.expenses_total ?? 0)})</h3>
              {(data.expense_items || []).map((e: any, i: number) => (
                <Row key={i} label={`${e.category} — ${e.description} (${e.date})`} amount={-e.amount} muted />
              ))}
            </div>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Worker Cashouts (-{fmtEGP(data.cashouts_total ?? 0)})</h3>
              {(data.cashout_items || []).map((w: any, i: number) => (
                <Row key={i} label={`${w.worker_name} (${w.date})`} amount={-w.amount_paid} muted />
              ))}
            </div>
          </>
        )}

        {type === "estimated" && (
          <>
            <p className={`text-2xl font-bold ${profitColor(data.total ?? 0)}`}>{fmtEGP(data.total ?? 0)}</p>
            <p className="text-xs text-muted-foreground">Period: {data.period_start} → {data.period_end}</p>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Billed Orders (+{fmtEGP(data.orders_total ?? 0)})</h3>
              {(data.order_items || []).map((o: any, i: number) => (
                <Row key={i} label={`#${o.invoice_number} — ${o.cx_name} (${o.date})`} amount={o.total} />
              ))}
              {(data.order_items || []).length === 0 && <p className="text-muted-foreground text-sm italic">No orders this week.</p>}
            </div>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Expenses (-{fmtEGP(data.expenses_total ?? 0)})</h3>
              {(data.expense_items || []).map((e: any, i: number) => (
                <Row key={i} label={`${e.category} — ${e.description}`} amount={-e.amount} muted />
              ))}
            </div>
            <div className="bg-card border rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-sm text-muted-foreground">Worker Salaries (-{fmtEGP(data.workers_total ?? 0)})</h3>
              {(data.worker_items || []).map((w: any, i: number) => (
                <Row key={i} label={w.name} amount={-w.weekly_salary} muted />
              ))}
              {(data.worker_items || []).length === 0 && <p className="text-muted-foreground text-sm italic">No active workers.</p>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);

  useEffect(() => {
    fetch(`${API}/dashboard/stats`)
      .then(r => r.json()).then(setStats)
      .catch(() => setError("Could not load dashboard stats."));
  }, []);

  const openBreakdown = async (type: "gross" | "net" | "estimated") => {
    setLoadingBreakdown(true);
    try {
      const res = await fetch(`${API}/dashboard/profit-breakdown?type=${type}`);
      const data = await res.json();
      setBreakdown({ type, data });
    } catch { /* ignore */ }
    setLoadingBreakdown(false);
  };

  if (error) return <p className="text-red-500 p-8">{error}</p>;
  if (!stats) return <p className="text-muted-foreground p-8">Loading dashboard...</p>;

  const ProfitCard = ({ label, value, type, sub }: {
    label: string; value: number; type: "gross" | "net" | "estimated"; sub?: string;
  }) => (
    <div className="bg-card border rounded-xl p-5 shadow-sm flex flex-col gap-1">
      <span className="text-sm text-muted-foreground font-medium">{label}</span>
      {}
      <span className={`text-3xl font-bold ${profitColor(value)}`}>{fmtEGP(value)}</span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
      <button
        onClick={() => openBreakdown(type)}
        disabled={loadingBreakdown}
        className="mt-2 self-start flex items-center gap-1 text-xs text-blue-500 hover:text-blue-400 disabled:opacity-50"
      >
        {loadingBreakdown ? <Loader2 size={12} className="animate-spin" /> : <ChevronRight size={12} />}
        View Breakdown
      </button>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <TrendingUp className="text-blue-500" /> Dashboard
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ProfitCard label="Gross Profit (All-Time)" value={stats.gross_profit} type="gross" />
        <ProfitCard label="Net Profit (Actual Cash)" value={stats.net_profit} type="net" />
        <ProfitCard
          label="Estimated Profit (This Week)"
          value={stats.estimated_profit}
          type="estimated"
          sub={`${stats.estimated_period_start} → ${stats.estimated_period_end}`}
        />
      </div>

      <div className="bg-card border rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4 border-b pb-2">Top 5 Most Sold Items (by Product ID)</h2>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={stats.top_items}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip formatter={(v: any) => [v, "Qty Sold"]} labelFormatter={l => `Product ID: ${l}`} />
              <Bar dataKey="qty" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card border rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 border-b pb-2 flex items-center gap-2">
            <Award size={18} className="text-amber-500" /> Top 3 Profitable Bills
          </h2>
          {stats.top_bills.map(b => (
            <div key={b.invoice_number} className="flex justify-between text-sm py-1.5 border-b last:border-0">
              <span>#{b.invoice_number} — {b.cx_name}</span>
              {}
              <span className="font-semibold text-amber-600">{fmtEGP(b.profit)}</span>
            </div>
          ))}
          {stats.top_bills.length === 0 && <p className="text-muted-foreground text-sm italic">No data.</p>}
        </div>

        <div className="bg-card border rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 border-b pb-2 flex items-center gap-2">
            <Users size={18} className="text-blue-500" /> Top 3 Profitable Customers
          </h2>
          {stats.top_customers.map((cu, i) => (
            <div key={i} className="flex justify-between text-sm py-1.5 border-b last:border-0">
              <span>{cu.name}</span>
              {}
              <span className="font-semibold text-amber-600">{fmtEGP(cu.profit)}</span>
            </div>
          ))}
          {stats.top_customers.length === 0 && <p className="text-muted-foreground text-sm italic">No data.</p>}
        </div>
      </div>

      {breakdown && <BreakdownPanel breakdown={breakdown} onClose={() => setBreakdown(null)} />}
    </div>
  );
}