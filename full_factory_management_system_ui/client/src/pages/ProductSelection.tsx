import { useState } from "react";
import { useLocation } from "wouter";
import { useInvoice } from "../contexts/InvoiceContext";
import { PackageSearch, Plus, Trash2, ChevronRight } from "lucide-react";
import InvoiceStepper from "../components/InvoiceStepper";

export default function ProductSelection() {
  const [, setLocation] = useLocation();
  const { cart, setCart } = useInvoice();
  const [tempId, setTempId] = useState("");

  const addProduct = (e: React.FormEvent) => {
    e.preventDefault();
    const id = parseInt(tempId);
    if (!isNaN(id)) {
      // Add to cart with a default quantity of 1
      setCart([...cart, { product_id: id, quantity: 1 }]);
      setTempId("");
    }
  };

  const removeProduct = (indexToRemove: number) => {
    setCart(cart.filter((_, index) => index !== indexToRemove));
  };

  return (
    <>
      <InvoiceStepper />
      <div className="max-w-2xl mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6 flex items-center gap-2">
        <PackageSearch className="text-blue-500" /> Add Items
      </h1>
      
      <div className="bg-card border rounded-xl p-6 shadow-sm space-y-6">
        <form onSubmit={addProduct} className="flex gap-3">
          <input 
            type="number" 
            value={tempId}
            onChange={(e) => setTempId(e.target.value)}
            className="flex-1 bg-background border rounded-md px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter Product ID (e.g., 1)"
          />
          <button type="submit" className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-md flex items-center gap-2">
            <Plus size={18} /> Add
          </button>
        </form>

        {/* Cart List */}
        <div className="space-y-2">
          {cart.map((item, idx) => (
            <div key={idx} className="flex justify-between items-center bg-background border p-3 rounded-md">
              <span className="font-mono">Product ID: {item.product_id}</span>
              <button onClick={() => removeProduct(idx)} className="text-red-500 hover:text-red-400">
                <Trash2 size={18} />
              </button>
            </div>
          ))}
          {cart.length === 0 && <p className="text-muted-foreground text-sm text-center py-4">Cart is empty. Add a Product ID.</p>}
        </div>

        <button 
          onClick={() => setLocation("/quantities")}
          disabled={cart.length === 0}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white font-semibold py-2 px-4 rounded-md flex justify-center items-center gap-2"
        >
          Next: Set Quantities <ChevronRight size={18} />
        </button>
      </div>
      </div>
    </>
  );
}