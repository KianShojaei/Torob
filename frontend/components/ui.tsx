"use client";

import React from "react";
import { ageLabel, fa, money } from "@/lib/format";

/* ------------------------------------------------------------------ icons */
type IconName =
  | "search" | "back" | "close" | "pin" | "filter" | "star" | "starOn"
  | "compare" | "chat" | "route" | "clock" | "check" | "warn" | "info"
  | "card" | "store" | "cart" | "home" | "arrow" | "spark" | "shield"
  | "phone" | "link" | "refresh" | "plus" | "minus" | "list" | "map";

const PATHS: Record<IconName, string> = {
  search: "M11 4a7 7 0 105.2 11.7l3.6 3.6 1.4-1.4-3.6-3.6A7 7 0 0011 4zm0 2a5 5 0 110 10 5 5 0 010-10z",
  back: "M15.4 4.6 8 12l7.4 7.4 1.4-1.4L10.8 12l6-6z",
  close: "M6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12 19 6.4 17.6 5 12 10.6z",
  pin: "M12 2a7 7 0 00-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 00-7-7zm0 9.5A2.5 2.5 0 1112 6.5a2.5 2.5 0 010 5z",
  filter: "M3 5h18v2H3V5zm3 6h12v2H6v-2zm3 6h6v2H9v-2z",
  star: "m12 3.6 2.5 5.1 5.6.8-4 3.9 1 5.6-5.1-2.7-5 2.7 1-5.6-4.1-3.9 5.6-.8L12 3.6z",
  starOn: "m12 3.6 2.5 5.1 5.6.8-4 3.9 1 5.6-5.1-2.7-5 2.7 1-5.6-4.1-3.9 5.6-.8L12 3.6z",
  compare: "M8 3H4v18h4v-2H6V5h2V3zm8 0v2h2v14h-2v2h4V3h-4zM10 8h2v8h-2V8zm4-3h2v14h-2V5z",
  chat: "M4 4h16v12H8l-4 4V4zm2 2v9.2L7.2 14H18V6H6z",
  route: "M7 3a3 3 0 013 3c0 2.2-3 6-3 6S4 8.2 4 6a3 3 0 013-3zm10 12a3 3 0 013 3c0 2.2-3 6-3 6s-3-3.8-3-6a3 3 0 013-3zM8 13v2h6a2 2 0 002-2V9h-2v4H8z",
  clock: "M12 2a10 10 0 100 20 10 10 0 000-20zm1 5h-2v6l5 3 1-1.6-4-2.4V7z",
  check: "M9.6 16.2 5.4 12l-1.4 1.4 5.6 5.6L20.4 8.2 19 6.8z",
  warn: "M12 2 1 21h22L12 2zm1 14h-2v2h2v-2zm0-7h-2v5h2V9z",
  info: "M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z",
  card: "M3 5h18v14H3V5zm2 3v2h14V8H5zm0 5v4h6v-4H5zm8 0v2h6v-2h-6zm0 3v1h6v-1h-6z",
  store: "M4 4h16l1 5H3l1-5zm-1 7h18v9H3v-9zm3 2v5h5v-5H6zm7 0v2h5v-2h-5zm0 3v2h5v-2h-5z",
  cart: "M7 4h2l1 2h9l-2 7H9L7.6 6H4V4h3zm2 13a2 2 0 100 4 2 2 0 000-4zm8 0a2 2 0 100 4 2 2 0 000-4z",
  home: "M12 3 2 12h3v9h6v-6h2v6h6v-9h3L12 3z",
  arrow: "M11 5.6 9.6 7l4 4H4v2h9.6l-4 4L11 18.4 17.4 12z",
  spark: "m12 2 2.2 6.6L21 11l-6.8 2.4L12 20l-2.2-6.6L3 11l6.8-2.4L12 2z",
  shield: "M12 2 4 5v7c0 5 3.4 8.6 8 10 4.6-1.4 8-5 8-10V5l-8-3zm-1 14-3.5-3.5 1.4-1.4L11 13.2l4.6-4.6 1.4 1.4L11 16z",
  phone: "M6.6 2.8 3 6.4c0 8 6.6 14.6 14.6 14.6l3.6-3.6-4.4-3.4-2.4 2.4a15 15 0 0 1-7-7l2.4-2.4L6.6 2.8z",
  link: "M10.6 13.4a1 1 0 0 1 0-1.4l3-3a3 3 0 0 1 4.2 4.2l-1.6 1.6-1.4-1.4 1.6-1.6a1 1 0 1 0-1.4-1.4l-3 3a1 1 0 0 1-1.4 0zM7.8 9.8l1.6-1.6 1.4 1.4-1.6 1.6a1 1 0 1 0 1.4 1.4l3-3a1 1 0 0 1 1.4 1.4l-3 3A3 3 0 0 1 7.8 9.8z",
  refresh: "M12 5V2L7 6l5 4V7a5 5 0 11-5 5H5a7 7 0 107-7z",
  plus: "M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z",
  minus: "M5 11h14v2H5z",
  list: "M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h16v2H4v-2z",
  map: "M9 2 3 4.6V22l6-2.6 6 2.6 6-2.6V2l-6 2.6L9 2zm1 3.2 4 1.7v11.9l-4-1.7V5.2z",
};

export function Icon({
  name,
  size = 20,
  filled = false,
  className = "",
}: {
  name: IconName;
  size?: number;
  filled?: boolean;
  className?: string;
}) {
  const d = name === "star" && filled ? PATHS.starOn : PATHS[name];
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill={name === "star" && filled ? "currentColor" : "currentColor"}
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}

/* ------------------------------------------------------------------ layout */
export function Screen({
  title,
  onBack,
  right,
  children,
  bottom,
  subtitle,
}: {
  title?: string;
  subtitle?: string;
  onBack?: () => void;
  right?: React.ReactNode;
  children: React.ReactNode;
  bottom?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col bg-[#f6f8fb]">
      {title && (
        <header className="sticky top-0 z-30 glass hairline">
          <div className="mx-auto flex max-w-md items-center gap-2 px-3 py-3">
            {onBack && (
              <button aria-label="بازگشت" onClick={onBack} className="rounded-full p-2 active:bg-slate-100">
                <Icon name="back" size={22} />
              </button>
            )}
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-[16px] font-bold leading-6">{title}</h1>
              {subtitle && <p className="truncate text-[11px] text-ink-500">{subtitle}</p>}
            </div>
            {right}
          </div>
        </header>
      )}
      <main className="mx-auto w-full max-w-md flex-1 px-3 pb-28">{children}</main>
      {bottom && (
        <div className="fixed inset-x-0 bottom-0 z-30 mx-auto max-w-md">
          <div className="glass border-t border-slate-200 px-3 pb-[calc(10px+var(--safe-bottom))] pt-2">
            {bottom}
          </div>
        </div>
      )}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function ProductSkeleton() {
  return (
    <div className="card flex gap-3 p-3">
      <Skeleton className="h-24 w-24 shrink-0 rounded-xl" />
      <div className="flex-1 space-y-2 py-1">
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-5 w-2/5" />
      </div>
    </div>
  );
}

/* ------------------------------------------------------- transparency bits */
export function PriceBlock({
  price,
  valid,
  ageBucket,
  ageDays,
  market,
  size = "md",
}: {
  price: number | null;
  valid: boolean;
  ageBucket?: string;
  ageDays?: number | null;
  market?: { delta_pct: number; label: string; tone: string } | null;
  size?: "sm" | "md" | "lg";
}) {
  const cls = size === "lg" ? "text-[22px]" : size === "sm" ? "text-[15px]" : "text-[18px]";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline gap-1.5">
        <span className={`num font-bold ${cls}`}>{valid ? money(price) : "نامشخص"}</span>
        {!valid && <span className="badge badge-unknown">قیمت نامعتبر</span>}
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <span className={`badge badge-${ageBucket || "unknown"}`}>
          <Icon name="clock" size={11} />
          ثبت‌شده: {ageLabel(ageBucket, ageDays)}
        </span>
        <span className="badge badge-unknown">
          <Icon name="info" size={11} />
          موجودی تأییدنشده
        </span>
        {market && (
          <span
            className={`badge ${
              market.tone === "good"
                ? "bg-brand-50 text-brand-700"
                : market.tone === "bad"
                  ? "bg-danger-50 text-danger-500"
                  : "bg-slate-100 text-ink-500"
            }`}
          >
            {fa(Math.abs(market.delta_pct).toFixed(0))}٪ {market.delta_pct <= 0 ? "زیر" : "بالای"} میانه
          </span>
        )}
      </div>
    </div>
  );
}

export function AvailabilityBadge({
  availability,
  source,
  at,
}: {
  availability: string;
  source?: string | null;
  at?: string | null;
}) {
  if (availability === "confirmed_in_stock") {
    return (
      <span className="badge bg-brand-600 text-white">
        <Icon name="check" size={11} /> موجودی تأییدشده{at ? ` · ${at}` : ""}
      </span>
    );
  }
  if (availability === "confirmed_out_of_stock") {
    return (
      <span className="badge bg-danger-50 text-danger-500">
        <Icon name="close" size={11} /> ناموجود (تأیید فروشنده)
      </span>
    );
  }
  return (
    <span className="badge bg-slate-100 text-ink-500">
      <Icon name="info" size={11} /> موجودی نامشخص
    </span>
  );
}

export function OpenBadge({
  state,
  opensAt,
  closesAt,
  onArrival,
}: {
  state: string;
  opensAt?: string | null;
  closesAt?: string | null;
  onArrival?: string | null;
}) {
  if (state === "open") {
    return (
      <span className="badge bg-brand-50 text-brand-700">
        <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />
        باز است{closesAt ? ` تا ${fa(closesAt)}` : ""}
      </span>
    );
  }
  if (state === "closed") {
    return (
      <span className="badge bg-danger-50 text-danger-500">
        <span className="h-1.5 w-1.5 rounded-full bg-danger-500" />
        بسته{opensAt ? ` · ${fa(opensAt)}` : ""}
      </span>
    );
  }
  if (onArrival === "closed") {
    return <span className="badge bg-warn-50 text-warn-500">با رسیدن شما بسته می‌شود</span>;
  }
  return (
    <span className="badge bg-slate-100 text-ink-500">
      <Icon name="info" size={11} /> ساعت کاری نامشخص
    </span>
  );
}

export function InstallmentBadge({ confirmed, declared }: { confirmed: boolean; declared: boolean }) {
  if (confirmed) {
    return (
      <span className="badge bg-brand-50 text-brand-700">
        <Icon name="card" size={11} /> اقساط حضوری تأییدشده
      </span>
    );
  }
  if (declared) {
    return (
      <span className="badge bg-slate-100 text-ink-500">
        <Icon name="card" size={11} /> اقساط اعلام‌شده (تأییدنشده)
      </span>
    );
  }
  return null;
}

export function DemoBadge({ text = "شبیه‌سازی" }: { text?: string }) {
  return (
    <span className="badge bg-accent-400/20 text-accent-600">
      <Icon name="spark" size={11} /> {text}
    </span>
  );
}

export function EmptyState({
  title,
  body,
  action,
  icon = "search",
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
  icon?: IconName;
}) {
  return (
    <div className="mt-10 flex flex-col items-center px-6 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-ink-300">
        <Icon name={icon} size={30} />
      </div>
      <h3 className="mb-1 text-[15px] font-bold">{title}</h3>
      <p className="mb-4 text-[13px] leading-6 text-ink-500">{body}</p>
      {action}
    </div>
  );
}

export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative w-full max-w-md animate-slideUp rounded-t-xl3 bg-white shadow-sheet">
        <div className="mx-auto mt-2 h-1.5 w-10 rounded-full bg-slate-200" />
        {title && (
          <div className="flex items-center justify-between px-4 pt-3">
            <h2 className="text-[15px] font-bold">{title}</h2>
            <button aria-label="بستن" onClick={onClose} className="rounded-full p-2 active:bg-slate-100">
              <Icon name="close" size={18} />
            </button>
          </div>
        )}
        <div className="sheet-scroll max-h-[78dvh] overflow-y-auto px-4 pb-[calc(18px+var(--safe-bottom))] pt-2">
          {children}
        </div>
      </div>
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string; icon?: IconName }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex rounded-2xl bg-slate-100 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`flex flex-1 items-center justify-center gap-1 rounded-xl py-2 text-[13px] font-medium transition ${
            value === o.value ? "bg-white text-ink-900 shadow-sm" : "text-ink-500"
          }`}
        >
          {o.icon && <Icon name={o.icon} size={15} />}
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Toast({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex justify-center">
      <div className="animate-pop rounded-full bg-ink-900/90 px-4 py-2 text-[13px] text-white shadow-lg">
        {text}
      </div>
    </div>
  );
}
