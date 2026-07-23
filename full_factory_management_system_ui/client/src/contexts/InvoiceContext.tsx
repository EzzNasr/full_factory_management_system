import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface CartItem {
  product_id: number;
  quantity: number;
}

interface InvoiceState {
  customerId: number;       // 0 means new customer, >0 means existing
  customerName: string;
  tierChoice: string;
  quantityType: string;     // "bulk" or "individual"
  cart: CartItem[];
  setCustomerId: (id: number) => void;
  setCustomerName: (name: string) => void;
  setTierChoice: (tier: string) => void;
  setQuantityType: (type: string) => void;
  setCart: (cart: CartItem[]) => void;
}

const InvoiceContext = createContext<InvoiceState | undefined>(undefined);

const STORAGE_KEY = "invoice_session_v1";

function loadPersisted() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function InvoiceProvider({ children }: { children: ReactNode }) {
  const persisted = loadPersisted();

  const [customerId, setCustomerId] = useState(persisted?.customerId ?? 0);
  const [customerName, setCustomerName] = useState(persisted?.customerName ?? "");
  const [tierChoice, setTierChoice] = useState(persisted?.tierChoice ?? "retail");
  const [quantityType, setQuantityType] = useState(persisted?.quantityType ?? "individual");
  const [cart, setCart] = useState<CartItem[]>(persisted?.cart ?? []);

  // Persist to sessionStorage on every change — survives a page refresh but
  // clears when the tab/browser closes, which matches "don't lose my
  // in-progress invoice on an accidental reload" without keeping stale
  // half-finished invoices around forever.
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        customerId, customerName, tierChoice, quantityType, cart,
      }));
    } catch {
      // sessionStorage can fail in some restricted/private-browsing contexts —
      // non-fatal, the app just falls back to in-memory-only for that session.
    }
  }, [customerId, customerName, tierChoice, quantityType, cart]);

  return (
    <InvoiceContext.Provider value={{
      customerId, setCustomerId,
      customerName, setCustomerName,
      tierChoice, setTierChoice,
      quantityType, setQuantityType,
      cart, setCart
    }}>
      {children}
    </InvoiceContext.Provider>
  );
}

export function useInvoice() {
  const context = useContext(InvoiceContext);
  if (!context) throw new Error("useInvoice must be used within an InvoiceProvider");
  return context;
}

export function clearInvoiceSession() {
  try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}