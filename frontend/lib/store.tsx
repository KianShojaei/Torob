"use client";

/** Tiny app store (React context + reducer) — no external state library. */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from "react";
import type { Neighborhood, Product, Store, ThreadStatus } from "./types";

export type View =
  | "home"
  | "products"
  | "stores"
  | "store"
  | "compare-products"
  | "compare-stores"
  | "contact"
  | "plan"
  | "saved";

export type Filters = {
  radius_km: number;
  max_price: number | null;
  installment: "off" | "confirmed" | "any";
  open_now: boolean;
  fresh_only: boolean;
  mall_only: boolean;
  sort: string;
};

export type Location = { label: string; lat: number; lon: number } | null;

type State = {
  view: View;
  history: View[];
  location: Location;
  query: string;
  category: string | null;
  budget: number | null;
  filters: Filters;
  products: Product[];
  selectedProducts: string[];
  activeProduct: Product | null;
  stores: Store[];
  activeStore: Store | null;
  threads: Record<string, ThreadStatus>;
  activeThread: string | null;
  compareStores: Store[];
  plan: any | null;
  saved: { products: Product[]; stores: Store[] };
  sessionId: string | null;
  meta: any | null;
  neighborhoods: Neighborhood[];
  chatOpen: boolean;
  messages: { role: "user" | "agent"; text: string; degraded?: boolean; cards?: string[] }[];
  loading: boolean;
};

const initial: State = {
  view: "home",
  history: [],
  location: null,
  query: "",
  category: null,
  budget: null,
  filters: {
    radius_km: 6,
    max_price: null,
    installment: "off",
    open_now: false,
    fresh_only: false,
    mall_only: false,
    sort: "balanced",
  },
  products: [],
  selectedProducts: [],
  activeProduct: null,
  stores: [],
  activeStore: null,
  threads: {},
  activeThread: null,
  compareStores: [],
  plan: null,
  saved: { products: [], stores: [] },
  sessionId: null,
  meta: null,
  neighborhoods: [],
  chatOpen: false,
  messages: [],
  loading: false,
};

type Action =
  | { type: "patch"; value: Partial<State> }
  | { type: "go"; view: View }
  | { type: "back" }
  | { type: "saveProduct"; product: Product }
  | { type: "saveStore"; store: Store }
  | { type: "toggleCompareProduct"; id: string }
  | { type: "toggleCompareStore"; store: Store };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "patch":
      return { ...state, ...action.value };
    case "go":
      return { ...state, view: action.view, history: [...state.history, state.view] };
    case "back": {
      const history = [...state.history];
      const prev = history.pop() || "home";
      return { ...state, view: prev as View, history };
    }
    case "saveProduct": {
      const exists = state.saved.products.some((p) => p.product_id === action.product.product_id);
      const products = exists
        ? state.saved.products.filter((p) => p.product_id !== action.product.product_id)
        : [...state.saved.products, action.product];
      return { ...state, saved: { ...state.saved, products } };
    }
    case "saveStore": {
      const exists = state.saved.stores.some((s) => s.shop_id === action.store.shop_id);
      const stores = exists
        ? state.saved.stores.filter((s) => s.shop_id !== action.store.shop_id)
        : [...state.saved.stores, action.store];
      return { ...state, saved: { ...state.saved, stores } };
    }
    case "toggleCompareProduct": {
      const has = state.selectedProducts.includes(action.id);
      const selected = has
        ? state.selectedProducts.filter((x) => x !== action.id)
        : [...state.selectedProducts, action.id].slice(0, 4);
      return { ...state, selectedProducts: selected };
    }
    case "toggleCompareStore": {
      const has = state.compareStores.some((s) => s.shop_id === action.store.shop_id);
      const list = has
        ? state.compareStores.filter((s) => s.shop_id !== action.store.shop_id)
        : [...state.compareStores, action.store].slice(0, 4);
      return { ...state, compareStores: list };
    }
    default:
      return state;
  }
}

const Ctx = createContext<{
  state: State;
  dispatch: React.Dispatch<Action>;
  set: (value: Partial<State>) => void;
  go: (view: View) => void;
  back: () => void;
} | null>(null);

const STORAGE = "torbgard:v1";

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);

  // hydrate saved items + last location
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE);
      if (raw) {
        const parsed = JSON.parse(raw);
        dispatch({
          type: "patch",
          value: {
            saved: parsed.saved || initial.saved,
            location: parsed.location || null,
            sessionId: parsed.sessionId || null,
          },
        });
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE,
        JSON.stringify({
          saved: state.saved,
          location: state.location,
          sessionId: state.sessionId,
        }),
      );
    } catch {
      /* quota */
    }
  }, [state.saved, state.location, state.sessionId]);

  const set = useCallback((value: Partial<State>) => dispatch({ type: "patch", value }), []);
  const go = useCallback((view: View) => dispatch({ type: "go", view }), []);
  const back = useCallback(() => dispatch({ type: "back" }), []);

  const value = useMemo(() => ({ state, dispatch, set, go, back }), [state, set, go, back]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
