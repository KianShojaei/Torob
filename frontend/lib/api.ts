/** Thin API client. Same-origin in production (FastAPI serves the PWA). */
import type { AgentEvent, Category, Neighborhood, Product, Store, ThreadStatus } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    ...options,
    headers: { "content-type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail || "";
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  meta: () => req<any>("/meta"),
  categories: () => req<{ categories: Category[] }>("/categories"),
  neighborhoods: () => req<{ neighbourhoods: Neighborhood[] }>("/neighbourhoods"),
  malls: () => req<{ malls: any[] }>("/malls"),

  search: (body: {
    query: string;
    category?: string | null;
    brand?: string | null;
    max_price?: number | null;
    min_price?: number | null;
    limit?: number;
  }) => req<{ products: Product[]; count: number; took_ms: number }>("/search", {
    method: "POST",
    body: JSON.stringify(body),
  }),

  product: (id: string) => req<{ product: Product }>(`/products/${id}`),

  compareProducts: (ids: string[]) =>
    req<{ products: Product[]; spec_rows: { spec: string; values: Record<string, string> }[]; cheapest_id: string }>(
      "/compare/products",
      { method: "POST", body: JSON.stringify({ product_ids: ids }) },
    ),

  stores: (body: {
    product_id: string;
    lat?: number | null;
    lon?: number | null;
    radius_km?: number;
    max_price?: number | null;
    installment?: string;
    open_now?: boolean;
    fresh_only?: boolean;
    mall_only?: boolean;
    neighborhood?: string | null;
    sort?: string;
    limit?: number;
  }) => req<{ stores: Store[]; count: number }>("/stores", {
    method: "POST",
    body: JSON.stringify(body),
  }),

  shop: (id: string, lat?: number | null, lon?: number | null) =>
    req<any>(`/shops/${id}${lat != null && lon != null ? `?lat=${lat}&lon=${lon}` : ""}`),

  compareStores: (body: { product_id: string; shop_ids: string[]; lat?: number | null; lon?: number | null }) =>
    req<{ rows: Store[]; cheapest_price: number | null }>("/compare/stores", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  contact: (body: {
    shop_id: string;
    product_id?: string | null;
    intent?: string;
    message?: string | null;
    channel?: string;
  }) => req<ThreadStatus & { will_reply?: boolean }>("/contact", { method: "POST", body: JSON.stringify(body) }),

  contactStatus: (id: string) => req<ThreadStatus>(`/contact/${id}`),

  alternatives: (body: {
    product_id: string;
    reason?: string;
    lat?: number | null;
    lon?: number | null;
    exclude_shop_ids?: string[];
    limit?: number;
  }) => req<any>("/alternatives", { method: "POST", body: JSON.stringify(body) }),

  plan: (body: {
    items: { shop_id: string; product_id?: string | null; price?: number | null }[];
    origin_lat?: number | null;
    origin_lon?: number | null;
    mode?: string;
  }) => req<any>("/plan", { method: "POST", body: JSON.stringify(body) }),

  event: (name: string, payload: Record<string, any> = {}, sessionId?: string) =>
    req<{ ok: boolean }>("/events", {
      method: "POST",
      body: JSON.stringify({ name, payload, session_id: sessionId }),
    }).catch(() => ({ ok: false })),
};

/** Streams agent events. Falls back to the non-streaming endpoint if SSE fails. */
export async function streamAgent(
  body: { message: string; session_id?: string; category?: string | null; lat?: number | null; lon?: number | null },
  onEvent: (e: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/agent/stream`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`stream_failed_${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as AgentEvent);
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
