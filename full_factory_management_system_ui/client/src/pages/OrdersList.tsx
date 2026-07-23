import { useState, useEffect } from "react";
import { Link } from "wouter";
import { ReceiptText } from "lucide-react";
import { API_BASE } from "../lib/api";

interface OrderItem { invoice_number: number; date: string; cx_name: string; }

export default function OrdersList() {
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/orders`).then(r => r.json()).then(d => { setOrders(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2"><ReceiptText className="text-blue-500" /> Orders</h1>
      <div className="bg-card border rounded-xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b bg-background/50">
              <th className="py-3 px-4">Invoice #</th>
              <th className="py-3 px-4">Date</th>
              <th className="py-3 px-4">Customer</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(o => (
              <tr key={o.invoice_number} className="border-b last:border-0 hover:bg-background/50">
                <td className="py-2 px-4">
                  <Link href={`/orders/${o.invoice_number}`} className="text-blue-600 hover:underline">#{o.invoice_number}</Link>
                </td>
                <td className="py-2 px-4 text-muted-foreground">{o.date}</td>
                <td className="py-2 px-4">{o.cx_name}</td>
              </tr>
            ))}
            {!loading && orders.length === 0 && (
              <tr><td colSpan={3} className="py-6 text-center text-muted-foreground italic">No orders yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}