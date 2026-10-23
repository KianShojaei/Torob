/** Persian formatting helpers: digits, money, Jalali dates, relative age. */

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export function fa(value: string | number): string {
  return String(value ?? "").replace(/\d/g, (d) => FA_DIGITS[Number(d)]);
}

export function faNum(value: number | string): string {
  return fa(Number(value).toLocaleString("en-US"));
}

export function money(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "نامشخص";
  return `${faNum(Math.round(value))} تومان`;
}

/** "۱٫۵ میلیون" for compact cards. */
export function moneyShort(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "نامشخص";
  if (value >= 1_000_000_000) return `${fa((value / 1_000_000_000).toFixed(1))} میلیارد`;
  if (value >= 1_000_000) return `${fa((value / 1_000_000).toFixed(1))} میلیون`;
  if (value >= 1_000) return `${fa(Math.round(value / 1000))} هزار`;
  return fa(Math.round(value));
}

export function priceRange(lo?: number | null, hi?: number | null): string {
  if (lo == null && hi == null) return "قیمت نامشخص";
  if (lo != null && hi != null && Math.round(lo) !== Math.round(hi)) {
    return `${moneyShort(lo)} تا ${moneyShort(hi)}`;
  }
  return moneyShort(lo ?? hi);
}

export function distance(km?: number | null, minutes?: number | null): string {
  if (km == null || km < 0) return "فاصله نامشخص";
  if (km < 1) return `${fa(Math.round((km * 1000) / 50) * 50)} متر`;
  const base = `${fa(km.toFixed(1))} کیلومتر`;
  return minutes ? `${base} · ${fa(minutes)} دقیقه` : base;
}

export function jalali(iso?: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return new Intl.DateTimeFormat("fa-IR", {
      calendar: "persian",
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(d);
  } catch {
    return "";
  }
}

export function jalaliShort(iso?: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
      month: "2-digit",
      day: "2-digit",
    }).format(d);
  } catch {
    return "";
  }
}

export function clock(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("fa-IR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

const AGE_LABEL: Record<string, string> = {
  fresh: "به‌روز",
  recent: "۲ تا ۴ هفته پیش",
  old: "قدیمی",
  stale: "خیلی قدیمی",
  unknown: "نامشخص",
};

export function ageLabel(bucket?: string | null, days?: number | null): string {
  if (bucket === "fresh" && days != null) {
    return days <= 0 ? "امروز" : `${fa(days)} روز پیش`;
  }
  return AGE_LABEL[bucket || "unknown"] || "نامشخص";
}

export function relativeSeconds(seconds?: number | null): string {
  if (seconds == null) return "";
  if (seconds <= 0) return "پایان یافته";
  if (seconds < 60) return `${fa(Math.ceil(seconds))} ثانیه`;
  return `${fa(Math.ceil(seconds / 60))} دقیقه`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0] || "").join("");
}
