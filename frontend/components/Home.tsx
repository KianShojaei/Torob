"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { fa, moneyShort } from "@/lib/format";
import { useApp } from "@/lib/store";
import type { Category, Neighborhood, Product } from "@/lib/types";
import ProductCard, { ProductImage } from "./ProductCard";
import { EmptyState, Icon, Sheet, Skeleton, Toast, DemoBadge } from "./ui";

const EXAMPLES = [
  "هدفون بلوتوثی زیر ۳ میلیون",
  "گوشی سامسونگ تا ۲۰ میلیون قسطی",
  "یخچال ساید بای ساید نزدیک سعادت‌آباد",
  "لپ‌تاپ برای برنامه‌نویسی تا ۵۰ میلیون",
];

export default function Home() {
  const { state, set, go } = useApp();
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState(state.query);
  const [locOpen, setLocOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [guided, setGuided] = useState<{ step: number; usage: string | null; budget: number | null } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.meta().then((m) => {
      set({ meta: m });
      if (!state.location) {
        set({ location: { label: "شیخ هادی", lat: m.default_location.lat, lon: m.default_location.lon } });
      }
    }).catch(() => setToast("اتصال به سرور برقرار نشد"));
    api.categories().then((r) => setCategories(r.categories.filter((c) => c.products > 0)));
    api.neighborhoods().then((r) => set({ neighborhoods: r.neighbourhoods }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSearch = async (text: string, category?: string | null, budget?: number | null) => {
    if (!text.trim() && !category && !budget) return;
    setLoading(true);
    set({ query: text, category: category ?? null, budget: budget ?? null });
    api.event("search_submitted", { text, category, budget }, state.sessionId || undefined);
    try {
      const res = await api.search({
        query: text,
        category: category ?? undefined,
        max_price: budget ?? undefined,
        limit: 12,
      });
      setProducts(res.products);
      set({ products: res.products, selectedProducts: [] });
      go("products");
    } catch {
      setToast("جست‌وجو ناموفق بود؛ دوباره تلاش کنید");
    } finally {
      setLoading(false);
    }
  };

  const suggested = useMemo(() => categories.slice(0, 8), [categories]);

  return (
    <div className="min-h-dvh pb-24">
      <Toast text={toast} />

      {/* header */}
      <header className="relative overflow-hidden bg-brand-700 pb-8 pt-4 text-white">
        <div className="absolute -left-16 -top-24 h-56 w-56 rounded-full bg-brand-500/40 blur-2xl" />
        <div className="absolute -right-10 top-10 h-40 w-40 rounded-full bg-accent-400/20 blur-2xl" />
        <div className="relative mx-auto max-w-md px-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-white/15">
                <Icon name="pin" size={19} />
              </div>
              <div>
                <p className="text-[10px] text-white/70">موقعیت خرید</p>
                <button onClick={() => setLocOpen(true)} className="flex items-center gap-1 text-[13px] font-bold">
                  {state.location?.label || "انتخاب محله"}
                  <Icon name="arrow" size={12} className="rotate-90" />
                </button>
              </div>
            </div>
            <button
              onClick={() => go("saved")}
              className="rounded-2xl bg-white/15 px-3 py-2 text-[12px] font-medium backdrop-blur"
            >
              ذخیره‌ها {state.saved.products.length + state.saved.stores.length > 0 &&
                `(${fa(state.saved.products.length + state.saved.stores.length)})`}
            </button>
          </div>

          <h1 className="mt-5 text-[24px] font-extrabold leading-9">
            قبل از اینکه راه بیفتی،
            <br />
            مطمئن شو.
          </h1>
          <p className="mt-1 text-[12px] leading-6 text-white/75">
            انتخاب مدل، فروشگاه نزدیک، تأیید قیمت و موجودی از خود فروشنده — همه در یک مسیر.
          </p>

          {/* search */}
          <div className="mt-4 flex items-center gap-2 rounded-2xl bg-white p-1.5 shadow-lg" dir="rtl">
            <span className="px-2 text-ink-300">
              <Icon name="search" size={19} />
            </span>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch(query)}
              placeholder="چی می‌خوای بخری؟"
              className="min-w-0 flex-1 bg-transparent py-2 text-[14px] text-ink-900 outline-none placeholder:text-ink-300"
            />
            <button
              onClick={() => runSearch(query)}
              className="rounded-xl bg-brand-600 px-4 py-2 text-[13px] font-bold text-white active:scale-95"
            >
              جست‌وجو
            </button>
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            <button
              onClick={() => {
                const next = !state.filters.open_now;
                set({ filters: { ...state.filters, open_now: next } });
                setToast(next ? "فقط فروشگاه‌های باز الان" : "همه فروشگاه‌ها");
              }}
              className={`rounded-full px-2.5 py-1 text-[11px] ${
                state.filters.open_now ? "bg-white text-brand-700" : "bg-white/15 text-white"
              }`}
            >
              باز الان
            </button>
            <button
              onClick={() => {
                const next = state.filters.installment === "confirmed" ? "off" : "confirmed";
                set({ filters: { ...state.filters, installment: next as any } });
                setToast(next === "confirmed" ? "فقط فروشگاه‌های اقساطی تأییدشده" : "فیلتر اقساط برداشته شد");
              }}
              className={`rounded-full px-2.5 py-1 text-[11px] ${
                state.filters.installment === "confirmed" ? "bg-white text-brand-700" : "bg-white/15 text-white"
              }`}
            >
              قسطی
            </button>
            <button
              onClick={() => setGuided({ step: 0, usage: null, budget: null })}
              className="rounded-full bg-white/15 px-2.5 py-1 text-[11px] text-white"
            >
              نمی‌دونم چی بخرم
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto -mt-4 max-w-md px-3">
        {/* categories */}
        <section className="card p-3">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-[13px] font-bold">دسته‌بندی‌ها</h2>
            <span className="text-[11px] text-ink-300">از دل دیتاست</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {suggested.length === 0 &&
              Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
            {suggested.map((c) => (
              <button
                key={c.name}
                onClick={() => runSearch("", c.name)}
                className="flex flex-col items-center justify-center gap-1 rounded-xl bg-slate-50 px-1 py-2.5 text-center active:scale-95"
              >
                <span className="text-ink-500">
                  <Icon name={iconFor(c.name)} size={19} />
                </span>
                <span className="line-clamp-2 text-[10px] leading-4 text-ink-700">
                  {shortCategory(c.name)}
                </span>
                <span className="num text-[9px] text-ink-300">{fa(c.products)}</span>
              </button>
            ))}
          </div>
        </section>

        {/* examples */}
        <section className="mt-3">
          <h2 className="mb-2 px-1 text-[13px] font-bold">مثال‌های واقعی</h2>
          <div className="flex gap-2 overflow-x-auto pb-1 sheet-scroll">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => runSearch(ex)}
                className="shrink-0 rounded-xl2 border border-slate-200 bg-white px-3 py-2 text-[12px] text-ink-700 active:scale-95"
              >
                {ex}
              </button>
            ))}
          </div>
        </section>

        {/* transparency */}
        <section className="mt-3 rounded-xl2 border border-dashed border-brand-200 bg-brand-50/60 p-3">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 text-brand-700">
              <Icon name="info" size={16} />
            </span>
            <div>
              <p className="text-[12px] font-bold text-brand-800">قیمت ثبت‌شده ≠ قیمت امروز</p>
              <p className="mt-0.5 text-[11px] leading-5 text-brand-700/80">
                قیمت‌های ترب مربوط به {fa(7)} روز پیش است. هر قیمت با برچسب تازگی و هر موجودی با وضعیت
                «تأییدنشده» نشان داده می‌شود تا با هم اشتباه نشوند.
              </p>
            </div>
          </div>
        </section>

        {state.meta?.is_synthetic && (
          <div className="mt-3 flex items-center justify-center">
            <DemoBadge text="داده‌ی نمایشی (ساختار واقعی دیتاست)" />
          </div>
        )}
      </div>

      {/* location sheet */}
      <Sheet open={locOpen} onClose={() => setLocOpen(false)} title="محله‌ی خرید">
        <button
          onClick={() => {
            navigator.geolocation?.getCurrentPosition(
              (pos) => {
                set({
                  location: {
                    label: "موقعیت من",
                    lat: pos.coords.latitude,
                    lon: pos.coords.longitude,
                  },
                });
                setLocOpen(false);
                setToast("موقعیت شما ثبت شد");
              },
              () => setToast("دسترسی به موقعیت ممکن نشد"),
            );
          }}
          className="btn-ghost mb-3 w-full"
        >
          <Icon name="pin" size={17} /> استفاده از موقعیت من
        </button>
        <p className="mb-2 text-[11px] text-ink-500">
          یا یکی از محله‌های موجود در دیتاست را انتخاب کنید (فروشگاه‌ها فقط در این مناطق ثبت شده‌اند):
        </p>
        <div className="grid grid-cols-2 gap-2">
          {state.neighborhoods.map((n: Neighborhood) => (
            <button
              key={n.label}
              onClick={() => {
                set({ location: { label: n.label, lat: n.lat, lon: n.lon } });
                setLocOpen(false);
              }}
              className={`flex items-center justify-between rounded-xl border px-3 py-2 text-[12px] ${
                state.location?.label === n.label
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-slate-200"
              }`}
            >
              <span>{n.label}</span>
              <span className="num text-[10px] text-ink-300">{fa(n.shop_count)}</span>
            </button>
          ))}
        </div>
      </Sheet>

      {/* guided model finder */}
      <Sheet
        open={!!guided}
        onClose={() => setGuided(null)}
        title={`راهنمای انتخاب مدل (${fa((guided?.step || 0) + 1)} از ۲)`}
      >
        {guided && (
          <div className="space-y-3 pb-2">
            {guided.step === 0 && (
              <>
                <p className="text-[13px] text-ink-500">این محصول را بیشتر برای چه کاری می‌خواهید؟</p>
                <div className="grid grid-cols-2 gap-2">
                  {["روزمره و پیاده‌روی", "استفاده حرفه‌ای", "بازی و سرگرمی", "هدیه"].map((u) => (
                    <button
                      key={u}
                      onClick={() => setGuided({ ...guided, step: 1, usage: u })}
                      className="rounded-xl border border-slate-200 px-3 py-3 text-[13px] active:bg-slate-50"
                    >
                      {u}
                    </button>
                  ))}
                </div>
              </>
            )}
            {guided.step === 1 && (
              <>
                <p className="text-[13px] text-ink-500">سقف بودجه‌تان چقدر است؟</p>
                <div className="grid grid-cols-2 gap-2">
                  {[2_000_000, 5_000_000, 15_000_000, 40_000_000].map((b) => (
                    <button
                      key={b}
                      onClick={async () => {
                        const chosen = b;
                        setGuided(null);
                        await runSearch("", state.category, chosen);
                      }}
                      className="rounded-xl border border-slate-200 px-3 py-3 text-[13px] active:bg-slate-50"
                    >
                      تا {moneyShort(b)} تومان
                    </button>
                  ))}
                </div>
                <button
                  onClick={async () => {
                    setGuided(null);
                    await runSearch("", state.category, null);
                  }}
                  className="w-full py-2 text-[12px] text-ink-500 underline"
                >
                  بودجه مهم نیست
                </button>
              </>
            )}
          </div>
        )}
      </Sheet>
    </div>
  );
}

function shortCategory(name: string): string {
  return name
    .replace("هدفون، هندزفری و اسپیکر", "صوتی")
    .replace("دوربین مداربسته و امنیتی", "دوربین")
    .replace("لپ‌تاپ و کامپیوتر", "لپ‌تاپ")
    .replace("تلویزیون و پروژکتور", "تلویزیون")
    .replace("یخچال و فریزر", "یخچال")
    .replace("کابل، سیم و کلید برق", "برق")
    .replace("مودم و تجهیزات شبکه", "شبکه")
    .replace("حافظه و ذخیره‌سازی", "حافظه")
    .replace("مانیتور و نمایشگر", "مانیتور")
    .replace("ساعت هوشمند و مچ‌بند", "ساعت")
    .replace("کیف و کوله پشتی", "کیف")
    .replace("روشنایی و لامپ", "روشنایی")
    .replace("لوازم خانگی", "خانه")
    .replace("گوشی موبایل", "موبایل");
}

function iconFor(name: string): any {
  if (name.includes("گوشی") || name.includes("تبلت")) return "phone";
  if (name.includes("لپ") || name.includes("مانیتور")) return "list";
  if (name.includes("یخچال") || name.includes("خانگی")) return "home";
  if (name.includes("روشنایی") || name.includes("برق")) return "spark";
  if (name.includes("دوربین")) return "shield";
  if (name.includes("صوتی") || name.includes("هدفون")) return "chat";
  if (name.includes("شبکه") || name.includes("حافظه")) return "link";
  if (name.includes("کفش") || name.includes("کیف") || name.includes("ساعت")) return "cart";
  return "store";
}
