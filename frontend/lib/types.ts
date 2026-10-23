export type Product = {
  product_id: string;
  title: string;
  brand: string | null;
  category: string | null;
  image: string | null;
  price_min: number | null;
  price_median: number | null;
  price_max: number | null;
  shop_count: number;
  offer_count?: number;
  key_specs: Record<string, string>;
  reasons?: string[];
  score?: number;
  badges?: string[];
  relation?: string;
};

export type MarketPosition = {
  delta_pct: number;
  label: string;
  tone: "good" | "neutral" | "warn" | "bad";
};

export type Store = {
  shop_id: string;
  name: string;
  name_is_real: boolean;
  lat?: number | null;
  lon?: number | null;
  category: string | null;
  location_label: string | null;
  distance_km: number;
  distance_note: string;
  travel_minutes: number;
  mode: string;
  price: number | null;
  price_valid: boolean;
  price_age_days: number | null;
  price_age_label: string;
  price_age_bucket: string;
  availability: string;
  availability_source: string | null;
  availability_at: string | null;
  market_position: MarketPosition | null;
  open_state: "open" | "closed" | "unknown";
  opens_at: string | null;
  closes_at: string | null;
  minutes_until_close: number | null;
  open_on_arrival: string | null;
  hours_known: boolean;
  installment_confirmed: boolean;
  installment_declared: boolean;
  installment_providers: string[];
  fast_delivery: "true" | "false" | "unknown";
  mall: {
    name: string | null;
    floor: string | null;
    unit: string | null;
    guide: {
      title: string;
      detail: string;
      known: string[];
      missing: string[];
      confidence: number;
      ask_sentence: string | null;
      landmark?: string | null;
    };
  };
  score: number;
  score_breakdown: Record<string, number>;
  reasons: string[];
  flags: string[];
  hours: { day: string; known: boolean; text: string; closed: boolean }[];
};

export type CardPayload = {
  kind:
    | "product_list"
    | "product_compare"
    | "store_list"
    | "store_compare"
    | "alternatives"
    | "mall_guide"
    | "visit_plan"
    | "contact_thread";
  payload: any;
};

export type AgentEvent =
  | { type: "text_delta"; text: string }
  | { type: "card"; card: CardPayload }
  | { type: "tool_status"; name: string; status: string; detail?: any }
  | { type: "state_update"; state: string; need?: any; session_id?: string }
  | { type: "done"; session_id: string; cards: string[]; degraded: boolean; latency_ms: number; provider: string }
  | { type: "error"; message: string };

export type Neighborhood = {
  label: string;
  lat: number;
  lon: number;
  shop_count: number;
};

export type Category = {
  name: string;
  products: number;
  offers: number;
  key_specs: string[];
  family: string[];
};

export type ThreadStatus = {
  thread_id: string;
  shop_id: string;
  product_id: string | null;
  intent: string;
  status: "sent" | "delivered" | "replied" | "no_reply" | "confirmed" | "out_of_stock" | "needs_followup";
  simulated: boolean;
  sent_at: string;
  replied_at: string | null;
  timeout_at: string;
  seconds_remaining: number | null;
  parsed: {
    in_stock: boolean | null;
    confirmed_price: number | null;
    unit: string | null;
    hours_info: string | null;
    needs_followup: boolean;
  } | null;
  messages: {
    role: "user" | "seller" | "system";
    body: string;
    created_at: string;
    meta?: any;
  }[];
};
