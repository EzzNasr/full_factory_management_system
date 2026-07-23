import { useState, useEffect } from "react";
import { useLocation } from "wouter";
import { useInvoice } from "../contexts/InvoiceContext";
import { User, ChevronRight, Users, UserPlus } from "lucide-react";
import InvoiceStepper from "../components/InvoiceStepper";
import { API_BASE } from "../lib/api";

export default function CustomerSelection() {
  const [, setLocation] = useLocation();
  const { customerId, setCustomerId, customerName, setCustomerName, tierChoice, setTierChoice } = useInvoice();

  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [dbCustomers, setDbCustomers] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string>(""); // controlled <select> value

  useEffect(() => {
    fetch(`${API_BASE}/customers`)
      .then(res => res.json())
      .then(data => setDbCustomers(data))
      .catch(err => console.error("Could not fetch customers:", err));
  }, []);

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (customerName.trim()) {
      setLocation("/products");
    }
  };

  // FIX: backend returns customer_id / default_tier, not id / tier.
  // FIX: guard against a null default_tier (new customers may have none yet).
  const selectExistingCustomer = (id: string) => {
    setSelectedId(id);
    const cust = dbCustomers.find(c => c.customer_id.toString() === id);
    if (cust) {
      setCustomerId(cust.customer_id);
      setCustomerName(cust.name);
      setTierChoice((cust.default_tier || "retail").toLowerCase());
    }
  };

  return (
    <>
      <InvoiceStepper />
      <div className="max-w-2xl mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6 text-foreground flex items-center gap-2">
        <User className="text-blue-500" /> Customer Details
      </h1>

      <div className="bg-card border rounded-xl p-6 shadow-sm space-y-6">
        {/* Toggle Tabs */}
        <div className="flex bg-background border rounded-lg p-1">
          <button
            type="button"
            onClick={() => {
              setMode("existing");
              // FIX: was dbCustomers[0]?.id - field doesn't exist, always fell to 0
              setCustomerId(dbCustomers[0]?.customer_id || 0);
              setSelectedId("");
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md font-medium transition-colors ${mode === "existing" ? "bg-primary text-primary-foreground shadow" : "text-muted-foreground hover:bg-muted"}`}
          >
            <Users size={18} /> Existing Customer
          </button>
          <button
            type="button"
            onClick={() => { setMode("new"); setCustomerId(0); setCustomerName(""); setSelectedId(""); }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md font-medium transition-colors ${mode === "new" ? "bg-primary text-primary-foreground shadow" : "text-muted-foreground hover:bg-muted"}`}
          >
            <UserPlus size={18} /> New Customer
          </button>
        </div>

        <form onSubmit={handleNext} className="space-y-6">
          {mode === "existing" ? (
            <div>
              <label className="block text-sm font-medium mb-2 text-muted-foreground">Select from Database</label>
              <select
                required
                value={selectedId}
                className="w-full bg-background border rounded-md px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
                onChange={(e) => selectExistingCustomer(e.target.value)}
              >
                <option value="">-- Choose a Customer --</option>
                {dbCustomers.map(c => (
                  <option key={c.customer_id} value={c.customer_id}>
                    [ID: {c.customer_id}] {c.name} - Tier: {c.default_tier || "—"}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium mb-2 text-muted-foreground">New Customer Name</label>
              <input
                type="text"
                required
                value={customerId === 0 ? customerName : ""}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full bg-background border rounded-md px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="e.g., Ezz Nasr"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-2 text-muted-foreground">Pricing Tier (Override if needed)</label>
            <select
              value={tierChoice}
              onChange={(e) => setTierChoice(e.target.value)}
              className="w-full bg-background border rounded-md px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
            >
              <option value="retail">Retail</option>
              <option value="wholesale">Wholesale</option>
            </select>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 px-4 rounded-md flex justify-center items-center gap-2"
          >
            Next: Add Products <ChevronRight size={18} />
          </button>
        </form>
      </div>
      </div>
    </>
  );
}