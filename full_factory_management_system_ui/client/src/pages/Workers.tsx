import { useState, useEffect } from "react";
import { Users, Plus, Trash2, DollarSign, History, X, UserX, UserCheck } from "lucide-react";
import { API_BASE } from "../lib/api";
import { fmtEGP } from "@/lib/format";

interface WorkerItem {
  worker_id: number;
  name: string;
  base_salary: number;
  active: number;
  balance_owed: number;
}

interface LedgerEntry {
  ledger_id: number;
  date: string;
  type: string; // 'salary' | 'bonus' | 'deduction'
  amount: number;
  note: string | null;
}


export default function Workers() {
  const [workers, setWorkers] = useState<WorkerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newWorker, setNewWorker] = useState({ name: "", base_salary: "" });
  const [creating, setCreating] = useState(false);

  const [panelWorker, setPanelWorker] = useState<WorkerItem | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [entryForm, setEntryForm] = useState({ type: "bonus", amount: "", note: "" });

  const inputCls = "w-full bg-background border rounded-md px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500";

  const loadWorkers = () => {
    setLoading(true);
    fetch(`${API_BASE}/workers`)
      .then(res => res.json())
      .then((data: WorkerItem[]) => { setWorkers(data); setLoading(false); })
      .catch(() => { setError("Could not load workers."); setLoading(false); });
  };

  useEffect(() => { loadWorkers(); }, []);

  const createWorker = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/workers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newWorker.name, base_salary: parseFloat(newWorker.base_salary) || 0 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      setNewWorker({ name: "", base_salary: "" });
      loadWorkers();
    } catch (err: any) {
      setError(`Failed to add worker: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (w: WorkerItem) => {
    const newActive = w.active ? 0 : 1;
    const verb = newActive ? "reactivate" : "deactivate";
    if (!confirm(`Are you sure you want to ${verb} ${w.name}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/workers/${w.worker_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: newActive }),
      });
      if (!res.ok) throw new Error("Update failed");
      loadWorkers();
    } catch {
      setError(`Failed to ${verb} worker.`);
    }
  };

  const deleteWorker = async (w: WorkerItem) => {
    if (!confirm(`Permanently delete ${w.name}? This only works if they have no payroll history.`)) return;
    try {
      const res = await fetch(`${API_BASE}/workers/${w.worker_id}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Delete failed");
      loadWorkers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const cashout = async (w: WorkerItem) => {
    if (!confirm(`Cash out ${w.name} for ${fmtEGP(w.balance_owed)}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/workers/${w.worker_id}/cashout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      loadWorkers();
    } catch (err: any) {
      setError(`Failed to cash out: ${err.message}`);
    }
  };

  const openPanel = async (w: WorkerItem) => {
    setPanelWorker(w);
    setEntryForm({ type: "bonus", amount: "", note: "" });
    const res = await fetch(`${API_BASE}/workers/${w.worker_id}/ledger`);
    const data = await res.json();
    setLedger(data.ledger ?? []);
  };

  const addLedgerEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!panelWorker) return;
    try {
      const rawAmount = parseFloat(entryForm.amount) || 0;
      const signedAmount = entryForm.type === "deduction" ? -Math.abs(rawAmount) : rawAmount;
      const res = await fetch(`${API_BASE}/workers/${panelWorker.worker_id}/ledger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: entryForm.type,
          amount: signedAmount,
          note: entryForm.note || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      setEntryForm({ type: "bonus", amount: "", note: "" });
      openPanel(panelWorker);
      loadWorkers();
    } catch (err: any) {
      setError(`Failed to add entry: ${err.message}`);
    }
  };

  if (loading) return <p className="p-8 text-muted-foreground">Loading workers...</p>;

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <Users className="text-blue-500" /> Workers
      </h1>

      {error && (
        <div className="bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg p-4 text-sm">{error}</div>
      )}

      {/* Add worker */}
      <div className="bg-card border rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4 border-b pb-2 flex items-center gap-2">
          <Plus size={18} /> Add Worker
        </h2>
        <form onSubmit={createWorker} className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
          <div className="col-span-2">
            <label className="block text-xs text-muted-foreground mb-1">Name</label>
            <input required type="text" value={newWorker.name} onChange={e => setNewWorker({ ...newWorker, name: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Weekly Base Salary</label>
            <input required type="number" step="0.01" value={newWorker.base_salary} onChange={e => setNewWorker({ ...newWorker, base_salary: e.target.value })} className={inputCls} />
          </div>
          <button type="submit" disabled={creating} className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2 rounded-md flex justify-center items-center gap-2">
            <Plus size={16} /> Add
          </button>
        </form>
      </div>

      {/* Worker list */}
      <div className="bg-card border rounded-xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b bg-background/50">
              <th className="py-3 px-4">Name</th>
              <th className="py-3 px-4">Base Salary</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Balance Owed</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {workers.map(w => (
              <tr key={w.worker_id} className="border-b last:border-0">
                <td className="py-2 px-4 font-medium">{w.name}</td>
                <td className="py-2 px-4">{fmtEGP(w.base_salary)}</td>
                <td className="py-2 px-4">
                  <span className={w.active ? "text-green-600" : "text-muted-foreground"}>
                    {w.active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="py-2 px-4 text-right font-semibold text-amber-600">{fmtEGP(w.balance_owed)}</td>
                <td className="py-2 px-4">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => openPanel(w)} title="Ledger" className="text-blue-500 hover:text-blue-400 p-1">
                      <History size={16} />
                    </button>
                    <button onClick={() => cashout(w)} title="Cash Out" className="text-green-600 hover:text-green-500 p-1">
                      <DollarSign size={16} />
                    </button>
                    <button onClick={() => toggleActive(w)} title={w.active ? "Deactivate" : "Reactivate"}
                      className={w.active ? "text-amber-600 hover:text-amber-500 p-1" : "text-green-600 hover:text-green-500 p-1"}>
                      {w.active ? <UserX size={16} /> : <UserCheck size={16} />}
                    </button>
                    <button onClick={() => deleteWorker(w)} title="Delete permanently" className="text-red-500 hover:text-red-400 p-1">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {workers.length === 0 && (
              <tr><td colSpan={5} className="py-6 text-center text-muted-foreground italic">No workers yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Ledger side panel */}
      {panelWorker && (
        <div className="fixed inset-0 bg-black/40 flex justify-end z-50" onClick={() => setPanelWorker(null)}>
          <div className="bg-card w-full max-w-md h-full p-6 overflow-y-auto space-y-6" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold">{panelWorker.name} — Ledger</h2>
              <button onClick={() => setPanelWorker(null)}><X size={20} /></button>
            </div>

            <form onSubmit={addLedgerEntry} className="space-y-3 bg-background border rounded-lg p-4">
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Type</label>
                <select value={entryForm.type} onChange={e => setEntryForm({ ...entryForm, type: e.target.value })} className={inputCls}>
                  <option value="salary">Salary</option>
                  <option value="bonus">Bonus</option>
                  <option value="deduction">Deduction</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">
                  Amount {entryForm.type === "deduction" ? "(enter positive, will be subtracted)" : ""}
                </label>
                <input required type="number" step="0.01" value={entryForm.amount} onChange={e => setEntryForm({ ...entryForm, amount: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Note</label>
                <input type="text" value={entryForm.note} onChange={e => setEntryForm({ ...entryForm, note: e.target.value })} className={inputCls} placeholder="e.g. overtime bonus" />
              </div>
              <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 rounded-md">Add Entry</button>
            </form>

            <div className="space-y-2">
              {ledger.map(entry => {
                const signedAmount = entry.type === "deduction" ? -Math.abs(entry.amount) : entry.amount;
                return (
                  <div key={entry.ledger_id} className="flex justify-between items-center bg-background border p-3 rounded-md text-sm">
                    <div>
                      <div className={signedAmount >= 0 ? "text-green-600 font-semibold" : "text-red-500 font-semibold"}>
                        {signedAmount >= 0 ? "+" : ""}{fmtEGP(signedAmount)} <span className="text-muted-foreground font-normal capitalize">({entry.type})</span>
                      </div>
                      <div className="text-muted-foreground text-xs">{entry.note || "—"}</div>
                    </div>
                    <span className="text-muted-foreground text-xs">{entry.date}</span>
                  </div>
                );
              })}
              {ledger.length === 0 && <p className="text-muted-foreground text-sm italic text-center py-4">No ledger entries yet.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}