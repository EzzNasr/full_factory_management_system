import { useState, useEffect } from "react";
import { Receipt, Plus, Trash2 } from "lucide-react";
import { API_BASE } from "../lib/api";
import { fmtEGP } from "@/lib/format";

interface ExpenseItem {
  expense_id: number;
  category: string;
  description: string | null;
  amount: number;
  date: string;
  notes: string | null;
}


function currentMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function Expenses() {
  const [expenses, setExpenses] = useState<ExpenseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [monthFilter, setMonthFilter] = useState(currentMonth());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    category: "utility",
    description: "",
    amount: "",
    date: today(),
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const load = (month: string) => {
    setLoading(true);
    fetch(`${API_BASE}/expenses?month=${month}`)
      .then(res => res.json())
      .then(data => {
        setExpenses(data.expenses ?? []);
        setTotal(data.total ?? 0);
        setLoading(false);
      })
      .catch(() => { setError("Could not load expenses."); setLoading(false); });
  };

  useEffect(() => { load(monthFilter); }, [monthFilter]);

  const addExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/expenses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: form.category,
          description: form.description,
          amount: parseFloat(form.amount) || 0,
          date: form.date,
          notes: form.notes || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      setForm({ category: "utility", description: "", amount: "", date: form.date, notes: "" });
      if (form.date.slice(0, 7) === monthFilter) load(monthFilter);
    } catch (err: any) {
      setError(`Failed to add expense: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const deleteExpense = async (id: number) => {
    if (!confirm("Delete this expense?")) return;
    try {
      const res = await fetch(`${API_BASE}/expenses/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
      load(monthFilter);
    } catch {
      setError("Failed to delete expense.");
    }
  };

  const inputCls = "w-full bg-background border rounded-md px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <Receipt className="text-blue-500" /> Expenses
      </h1>

      {error && (
        <div className="bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg p-4 text-sm">{error}</div>
      )}

      {/* Add form */}
      <div className="bg-card border rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4 border-b pb-2 flex items-center gap-2">
          <Plus size={18} /> Log Expense
        </h2>
        <form onSubmit={addExpense} className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Category</label>
            <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className={inputCls}>
              <option value="utility">Utility</option>
              <option value="misc">Misc</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-muted-foreground mb-1">Description</label>
            <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className={inputCls} placeholder="e.g. Electricity bill" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Amount</label>
            <input required type="number" step="0.01" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Date</label>
            <input required type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Notes</label>
            <input type="text" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className={inputCls} />
          </div>
          <button type="submit" disabled={submitting} className="col-span-2 md:col-span-6 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2 rounded-md flex justify-center items-center gap-2">
            <Plus size={16} /> Add Expense
          </button>
        </form>
      </div>

      {/* Filter + total */}
      <div className="flex items-center justify-between">
        <input type="month" value={monthFilter} onChange={e => setMonthFilter(e.target.value)} className={`${inputCls} w-48`} />
        <div className="text-lg font-semibold">Total: <span className="text-amber-600">{fmtEGP(total)}</span></div>
      </div>

      {/* List */}
      <div className="bg-card border rounded-xl shadow-sm overflow-x-auto">
        {loading ? (
          <p className="p-6 text-muted-foreground">Loading...</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground border-b bg-background/50">
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Description</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Notes</th>
                <th className="py-3 px-4 text-right">Amount</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {expenses.map(e => (
                <tr key={e.expense_id} className="border-b last:border-0">
                  <td className="py-2 px-4 capitalize">{e.category}</td>
                  <td className="py-2 px-4">{e.description || "—"}</td>
                  <td className="py-2 px-4 text-muted-foreground">{e.date}</td>
                  <td className="py-2 px-4 text-muted-foreground">{e.notes || "—"}</td>
                  <td className="py-2 px-4 text-right font-semibold">{fmtEGP(e.amount)}</td>
                  <td className="py-2 px-4 text-right">
                    <button onClick={() => deleteExpense(e.expense_id)} className="text-red-500 hover:text-red-400 p-1">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
              {expenses.length === 0 && (
                <tr><td colSpan={6} className="py-6 text-center text-muted-foreground italic">No expenses logged for this month.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}