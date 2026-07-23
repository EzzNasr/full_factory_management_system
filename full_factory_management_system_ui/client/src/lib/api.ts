// src/lib/api.ts
//
// Single source of truth for the backend base URL. Set VITE_API_URL in a
// .env file (or via `set VITE_API_URL=... && npm run dev` / Cloudflare
// Tunnel setups) to point the frontend at a non-localhost backend — e.g.
// when sharing the app through a tunnel, localhost:8000 only resolves on
// YOUR machine, not the machine opening your tunnel link.
//
// Usage in any page/component:
//   import { API_BASE } from "../lib/api";
//   fetch(`${API_BASE}/orders`)

export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
