import { useState, useEffect } from "react";
import { Boxes, Plus, Trash2, Save, RotateCcw } from "lucide-react";
import { API_BASE } from "../lib/api";

interface Product {
  product_id: number;
  item_name: string;
  retail_price: number;
  wholesale_price: number;
  cost: number;
  stock_quantity: number | null;
}

type EditableProduct = {
  item_name: string;
  retail_price: string;
  wholesale_price: string;
  cost: string;
  stock_quantity: string;
};


function toEditable(p: Product): EditableProduct {
  return {
    item_name: p.item_name,
    retail_price: String(p.retail_price),
    wholesale_price: String(p.wholesale_price),
    cost: String(p.cost),
    stock_quantity: p.stock_quantity === null ? "" : String(p.stock_quantity),
  };
}

export default function ProductsManager() {
  const [products, setProducts] = useState<Product[]>([]);
  const [edits, setEdits] = useState<Record<number, EditableProduct>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [newProduct, setNewProduct] = useState({
    product_id: "", item_name: "", retail_price: "", wholesale_price: "", cost: "", stock_quantity: "",
  });
  const [creating, setCreating] = useState(false);

  const loadProducts = () => {
    setLoading(true);
    fetch(`${API_BASE}/products`)
      .then(res => res.json())
      .then((data: Product[]) => {
        setProducts(data);
        const editMap: Record<number, EditableProduct> = {};
        data.forEach(p => { editMap[p.product_id] = toEditable(p); });
        setEdits(editMap);
        setLoading(false);
      })
      .catch(() => { setError("Could not load products."); setLoading(false); });
  };

  useEffect(() => { loadProducts(); }, []);

  const updateField = (id: number, field: keyof EditableProduct, value: string) => {
    setEdits(prev => ({ ...prev, [id]: { ...prev[id], [field]: value } }));
  };

  const resetRow = (p: Product) => {
    setEdits(prev => ({ ...prev, [p.product_id]: toEditable(p) }));
  };

  const saveRow = async (id: number) => {
    const e = edits[id];
    setSavingId(id);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/products/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_name: e.item_name,
          retail_price: parseFloat(e.retail_price) || 0,
          wholesale_price: parseFloat(e.wholesale_price) || 0,
          cost: parseFloat(e.cost) || 0,
          stock_quantity: e.stock_quantity === "" ? null : parseInt(e.stock_quantity),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      setProducts(prev => prev.map(p => (p.product_id === id ? data : p)));
      setEdits(prev => ({ ...prev, [id]: toEditable(data) }));
    } catch (err: any) {
      setError(`Failed to save product ${id}: ${err.message}`);
    } finally {
      setSavingId(null);
    }
  };

  const deleteRow = async (id: number) => {
    if (!confirm(`Delete product ${id}? This cannot be undone.`)) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/products/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      setProducts(prev => prev.filter(p => p.product_id !== id));
    } catch (err: any) {
      setError(`Failed to delete product ${id}: ${err.message}`);
    }
  };

  const createProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id: parseInt(newProduct.product_id),
          item_name: newProduct.item_name,
          retail_price: parseFloat(newProduct.retail_price) || 0,
          wholesale_price: parseFloat(newProduct.wholesale_price) || 0,
          cost: parseFloat(newProduct.cost) || 0,
          stock_quantity: newProduct.stock_quantity === "" ? null : parseInt(newProduct.stock_quantity),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data.detail));
      setNewProduct({ product_id: "", item_name: "", retail_price: "", wholesale_price: "", cost: "", stock_quantity: "" });
      loadProducts();
    } catch (err: any) {
      setError(`Failed to create product: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const inputCls = "w-full bg-background border rounded-md px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-blue-500";

  if (loading) return <p className="p-8 text-muted-foreground">Loading products...</p>;

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <Boxes className="text-blue-500" /> Products
      </h1>

      {error && (
        <div className="bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      <div className="bg-card border rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4 border-b pb-2 flex items-center gap-2">
          <Plus size={18} /> Add New Product
        </h2>
        <form onSubmit={createProduct} className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Product ID</label>
            <input required type="number" value={newProduct.product_id}
              onChange={e => setNewProduct({ ...newProduct, product_id: e.target.value })} className={inputCls} />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-muted-foreground mb-1">Name</label>
            <input required type="text" value={newProduct.item_name}
              onChange={e => setNewProduct({ ...newProduct, item_name: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Retail</label>
            <input required type="number" step="0.01" value={newProduct.retail_price}
              onChange={e => setNewProduct({ ...newProduct, retail_price: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Wholesale</label>
            <input required type="number" step="0.01" value={newProduct.wholesale_price}
              onChange={e => setNewProduct({ ...newProduct, wholesale_price: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Cost</label>
            <input required type="number" step="0.01" value={newProduct.cost}
              onChange={e => setNewProduct({ ...newProduct, cost: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Stock (blank = untracked)</label>
            <input type="number" value={newProduct.stock_quantity}
              onChange={e => setNewProduct({ ...newProduct, stock_quantity: e.target.value })} className={inputCls} />
          </div>
          <button type="submit" disabled={creating}
            className="col-span-2 md:col-span-1 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2 rounded-md flex justify-center items-center gap-2">
            <Plus size={16} /> Add
          </button>
        </form>
      </div>

      <div className="bg-card border rounded-xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b bg-background/50">
              <th className="py-3 px-4">ID</th>
              <th className="py-3 px-4">Name</th>
              <th className="py-3 px-4">Retail</th>
              <th className="py-3 px-4">Wholesale</th>
              <th className="py-3 px-4">Cost</th>
              <th className="py-3 px-4">Stock</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {products.map(p => {
              const e = edits[p.product_id];
              if (!e) return null;
              const dirty = JSON.stringify(e) !== JSON.stringify(toEditable(p));
              return (
                <tr key={p.product_id} className="border-b last:border-0">
                  <td className="py-2 px-4 font-mono text-muted-foreground">{p.product_id}</td>
                  <td className="py-2 px-4"><input className={inputCls} value={e.item_name}
                    onChange={ev => updateField(p.product_id, "item_name", ev.target.value)} /></td>
                  <td className="py-2 px-4 w-24"><input type="number" step="0.01" className={inputCls} value={e.retail_price}
                    onChange={ev => updateField(p.product_id, "retail_price", ev.target.value)} /></td>
                  <td className="py-2 px-4 w-24"><input type="number" step="0.01" className={inputCls} value={e.wholesale_price}
                    onChange={ev => updateField(p.product_id, "wholesale_price", ev.target.value)} /></td>
                  <td className="py-2 px-4 w-24"><input type="number" step="0.01" className={inputCls} value={e.cost}
                    onChange={ev => updateField(p.product_id, "cost", ev.target.value)} /></td>
                  <td className="py-2 px-4 w-24">
                    <input type="number" className={inputCls} placeholder="untracked" value={e.stock_quantity}
                      onChange={ev => updateField(p.product_id, "stock_quantity", ev.target.value)} />
                  </td>
                  <td className="py-2 px-4">
                    <div className="flex justify-end gap-2">
                      {dirty && (
                        <button onClick={() => resetRow(p)} title="Discard changes"
                          className="text-muted-foreground hover:text-foreground p-1">
                          <RotateCcw size={16} />
                        </button>
                      )}
                      <button onClick={() => saveRow(p.product_id)} disabled={!dirty || savingId === p.product_id}
                        title="Save" className="text-blue-500 hover:text-blue-400 disabled:opacity-30 p-1">
                        <Save size={16} />
                      </button>
                      <button onClick={() => deleteRow(p.product_id)} title="Delete"
                        className="text-red-500 hover:text-red-400 p-1">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {products.length === 0 && (
              <tr><td colSpan={7} className="py-6 text-center text-muted-foreground italic">No products yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}