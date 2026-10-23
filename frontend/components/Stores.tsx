"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { fa, moneyShort } from "@/lib/format";
import { useApp } from "@/lib/store";
import type { Store } from "@/lib/types";
import MapView from "./MapView";
import StoreCard from "./StoreCard";
import { EmptyState, Icon, Screen, Segmented, Sheet, Skeleton, Toast } from "./ui";

const SORT_CHIPS = [
  { value: "balanced", label: "بهترین ترکیب" },
  { value: "cheapest", label: "ارزان‌ترین" },
  { value: "nearest", label: "نزدیک‌ترین" },
  { value: "open_now", label: "باز الان" },
  { value: "trusted", label: "مطمئن‌ترین" },
];

export default function Stores() {
  const { state, set, go, back } = useApp();
  const [mode, setMode] = useState<"list" | "map">("list");
  const [stores, setStores] = useState<Store[]>(state.stores);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const product = state.activeProduct;
  const loc = state.location;
  const filters = state.filters;

  const load = useCallback(async () => {
    if (!product) return;
    setLoading(true);
    try {
      const res = await api.stores({
        product_id: product.product_id,
        lat: loc?.lat,
        lon: loc?.lon,
        radius_km: filters.radius_km,
        max_price: filters.max_price,
        installment: filters.installment,
        open_now: filters.open_now,
        fresh_only: filters.fresh_only,
        mall_only: filters.mall_only,
        sort: filters.sort,
        limit: 40,
      });
      setStores(res.stores);
      set({ stores: res.stores });
    } catch {
      setToast("دریافت فروشگاه‌ها ناموفق بود");
    } finally {
      setLoading(false);
    }
  }, [product, loc?.lat, loc?.lon, filters, set]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, product?.product_id, loc?.lat, loc?.lon]);

  const patchFilters = (patch: Partial<typeof filters>) => {
    set({ filters: { ...filters, ...patch } });
  };

  const center = { lat: loc?.lat ?? 35.6949, lon: loc?.lon ?? 51.4071 };
  const stats = useMemo(() => {
    const prices = stores.filter((s) => s.price_valid && s.price).map((s) => s.price as number);
    return {
      min: prices.length ? Math.min(...prices) : null,
      max: prices.length ? Math.max(...prices) : null,
      open: stores.filter((s) => s.open_state === "open").length,
      installment: stores.filter((s) => s.installment_confirmed).length,
    };
  }, [stores]);

  const startContact = async (store: Store) => {
    try {
      const t = await api.contact({
        shop_id: store.shop_id,
        product_id: product?.product_id,
        intent: "price_stock",
      });
      const threads = { ...state.threads, [t.thread_id]: t };
      set({ threads, activeThread: t.thread_id });
      go("contact");
    } catch {
      setToast("ارسال درخواست ناموفق بود");
    }
  };

  return (
    <Screen
      title={product?.title || "فروشگاه‌ها"}
      subtitle={`${fa(stores.length)} فروشگاه · ${loc?.label || "بدون موقعیت"}`}
      onBack={back}
      right={
        <button onClick={() => go("plan")} aria-label="برنامه سفر" className="rounded-full p-2 active:bg-slate-100">
          <Icon name="route" size={20} />
        </button>
      }
      bottom={
        <div className="flex items-center gap-2">
          <button onClick={() => setFilterOpen(true)} className="btn-ghost flex-1 py-2.5 text-[13px]">
            <Icon name="filter" size={16} />
            فیلترها
            {(filters.installment !== "off" || filters.open_now || filters.fresh_only) && (
              <span className="h-1.5 w-1.5 rounded-full bg-accent-500" />
            )}
          </button>
          {state.compareStores.length > 0 ? (
            <button onClick={() => go("compare-stores")} className="btn-primary flex-1 py-2.5 text-[13px]">
              مقایسه ({fa(state.compareStores.length)})
            </button>
          ) : (
            <button onClick={() => setMode(mode === "list" ? "map" : "list")} className="btn-primary flex-1 py-2.5 text-[13px]">
              <Icon name={mode === "list" ? "map" : "list"} size={16} />
              {mode === "list" ? "نقشه" : "لیست"}
            </button>
          )}
        </div>
      }
    >
      <Toast text={toast} />

      {/* quick stats */}
      <div className="mt-2 grid grid-cols-4 gap-1.5">
        <Stat label="کمترین" value={stats.min ? moneyShort(stats.min) : "—"} />
        <Stat label="بیشترین" value={stats.max ? moneyShort(stats.max) : "—"} />
        <Stat label="باز الان" value={fa(stats.open)} />
        <Stat label="اقساطی" value={fa(stats.installment)} />
      </div>

      {/* sort chips */}
      <div className="flex gap-1.5 overflow-x-auto py-2 sheet-scroll">
        {SORT_CHIPS.map((s) => (
          <button
            key={s.value}
            onClick={() => patchFilters({ sort: s.value, ...(s.value === "open_now" ? { open_now: true } : { open_now: false }) })}
            data-on={filters.sort === s.value}
            className="chip"
          >
            {s.label}
          </button>
        ))}
      </div>

      {mode === "map" && (
        <div className="mb-3">
          <MapView stores={stores} center={center} selectedId={selected} onSelect={setSelected} />
          <p className="mt-1 text-center text-[10px] text-ink-300">
            قیمت روی هر پین = قیمت ثبت‌شده‌ی همان فروشگاه
          </p>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card space-y-2 p-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-2/3" />
              <Skeleton className="h-8 w-1/3" />
            </div>
          ))}
        </div>
      ) : stores.length === 0 ? (
        <EmptyState
          icon="store"
          title="فروشگاهی با این فیلترها نیست"
          body="شعاع را بیشتر کنم یا فیلتر اقساط را بردارم؟"
          action={
            <div className="flex gap-2">
              <button className="btn-soft" onClick={() => patchFilters({ radius_km: filters.radius_km + 5 })}>
                شعاع بیشتر
              </button>
              <button className="btn-ghost" onClick={() => patchFilters({ installment: "off", open_now: false, fresh_only: false })}>
                حذف فیلترها
              </button>
            </div>
          }
        />
      ) : (
        <div className="space-y-2.5">
          {stores.map((s) => (
            <StoreCard
              key={s.shop_id}
              store={s}
              inCompare={state.compareStores.some((x) => x.shop_id === s.shop_id)}
              onOpen={() => {
                set({ activeStore: s });
                go("store");
              }}
              onContact={() => startContact(s)}
              onCompare={() => {
                const has = state.compareStores.some((x) => x.shop_id === s.shop_id);
                const list = has
                  ? state.compareStores.filter((x) => x.shop_id !== s.shop_id)
                  : [...state.compareStores, s].slice(0, 4);
                set({ compareStores: list });
                setToast(has ? "از مقایسه حذف شد" : "به مقایسه اضافه شد");
              }}
              onShowGuide={() => {
                set({ activeStore: s });
                go("store");
              }}
            />
          ))}
        </div>
      )}

      <Sheet open={filterOpen} onClose={() => setFilterOpen(false)} title="فیلترها">
        <div className="space-y-4 pb-3">
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-[13px] font-semibold">شعاع جست‌وجو</label>
              <span className="num text-[12px] text-brand-700">{fa(filters.radius_km)} کیلومتر</span>
            </div>
            <input
              type="range"
              min={1}
              max={25}
              step={1}
              value={filters.radius_km}
              onChange={(e) => patchFilters({ radius_km: Number(e.target.value) })}
              className="w-full accent-brand-600"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold">سقف بودجه</label>
            <div className="flex gap-1.5 overflow-x-auto sheet-scroll">
              {[null, 2_000_000, 5_000_000, 15_000_000, 40_000_000, 100_000_000].map((b) => (
                <button
                  key={String(b)}
                  onClick={() => patchFilters({ max_price: b })}
                  data-on={filters.max_price === b}
                  className="chip"
                >
                  {b ? `تا ${moneyShort(b)}` : "بدون سقف"}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold">شرایط خرید</label>
            <div className="space-y-2">
              <Toggle
                label="فقط فروشگاه‌هایی که اقساط حضوری تأییدشده دارند"
                hint="فیلتر سخت: فروشگاه بدون ارائه‌دهنده کنار گذاشته می‌شود"
                checked={filters.installment === "confirmed"}
                onChange={(v) => patchFilters({ installment: v ? "confirmed" : "off" })}
              />
              <Toggle
                label="فقط باز الان"
                checked={filters.open_now}
                onChange={(v) => patchFilters({ open_now: v })}
              />
              <Toggle
                label="فقط قیمت‌های به‌روز (۷ روز اخیر)"
                checked={filters.fresh_only}
                onChange={(v) => patchFilters({ fresh_only: v })}
              />
              <Toggle
                label="فقط داخل پاساژ"
                checked={filters.mall_only}
                onChange={(v) => patchFilters({ mall_only: v })}
              />
            </div>
          </div>

          <button className="btn-primary w-full" onClick={() => setFilterOpen(false)}>
            نمایش {fa(stores.length)} نتیجه
          </button>
        </div>
      </Sheet>
    </Screen>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white px-2 py-1.5 text-center">
      <p className="num text-[12px] font-bold text-ink-900">{value}</p>
      <p className="text-[9px] text-ink-300">{label}</p>
    </div>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2 text-right"
    >
      <span className="min-w-0">
        <span className="block text-[12px] font-medium">{label}</span>
        {hint && <span className="mt-0.5 block text-[10px] text-ink-300">{hint}</span>}
      </span>
      <span
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${
          checked ? "bg-brand-600" : "bg-slate-200"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${
            checked ? "right-0.5" : "right-[22px]"
          }`}
        />
      </span>
    </button>
  );
}
