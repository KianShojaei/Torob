"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fa, money } from "@/lib/format";
import { useApp } from "@/lib/store";
import { EmptyState, Icon, Screen, Skeleton, Toast } from "./ui";

export default function Plan() {
  const { state, back, set, go } = useApp();
  const [plan, setPlan] = useState<any>(state.plan);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const items =
    state.compareStores.length > 0
      ? state.compareStores.map((s) => ({
          shop_id: s.shop_id,
          product_id: state.activeProduct?.product_id,
          price: s.price,
        }))
      : state.saved.stores.map((s) => ({ shop_id: s.shop_id, product_id: null, price: s.price }));

  const build = async () => {
    if (items.length === 0) return;
    setLoading(true);
    try {
      const res = await api.plan({
        items,
        origin_lat: state.location?.lat,
        origin_lon: state.location?.lon,
        mode: "car",
      });
      setPlan(res);
      set({ plan: res });
    } catch {
      setToast("ساخت برنامه ناموفق بود");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!plan && items.length > 0) build();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Screen
      title="برنامه‌ی سفر خرید"
      subtitle={`${fa(items.length)} توقف · شروع از ${state.location?.label || "موقعیت شما"}`}
      onBack={back}
      bottom={
        plan?.stops?.length ? (
          <div className="flex gap-2">
            <a
              className="btn-primary flex-1 py-2.5 text-[13px]"
              href={`https://www.google.com/maps/dir/${plan.stops
                .map((s: any) => `${s.lat},${s.lon}`)
                .join("/")}`}
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="route" size={16} /> شروع مسیریابی
            </a>
            <button
              className="btn-ghost py-2.5 text-[13px]"
              onClick={async () => {
                const text = plan.stops
                  .map((s: any, i: number) => `${i + 1}. ${s.shop_name} — ${s.arrival_time}`)
                  .join("\n");
                try {
                  await navigator.clipboard.writeText(`برنامه‌ی خرید من:\n${text}`);
                  setToast("برنامه کپی شد");
                } catch {
                  setToast("کپی ممکن نشد");
                }
              }}
            >
              کپی
            </button>
          </div>
        ) : undefined
      }
    >
      <Toast text={toast} />

      {items.length === 0 && (
        <EmptyState
          icon="route"
          title="هنوز فروشگاهی انتخاب نکرده‌اید"
          body="از صفحه‌ی فروشگاه‌ها دو یا سه مغازه را به مقایسه اضافه کنید تا مسیر بهینه ساخته شود."
          action={
            <button className="btn-soft" onClick={() => go("stores")}>
              انتخاب فروشگاه
            </button>
          }
        />
      )}

      {loading && (
        <div className="mt-3 space-y-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      )}

      {plan?.warnings?.length > 0 && (
        <div className="mt-2 rounded-xl2 border border-warn-500/30 bg-warn-50 p-3">
          <p className="mb-1 flex items-center gap-1 text-[12px] font-bold text-warn-500">
            <Icon name="warn" size={14} /> هشدارهای ساعت کاری
          </p>
          {plan.warnings.map((w: string) => (
            <p key={w} className="text-[11px] leading-5 text-ink-700">
              • {w}
            </p>
          ))}
        </div>
      )}

      {plan?.stops?.length > 0 && (
        <div className="mt-3 space-y-2">
          {plan.stops.map((s: any, i: number) => (
            <div key={s.shop_id} className="card relative p-3 pr-10">
              <span className="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-[11px] font-bold text-white">
                {fa(i + 1)}
              </span>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-bold">{s.shop_name}</p>
                  <p className="mt-0.5 text-[10px] text-ink-300">
                    {s.mall?.title || s.mall?.name || "بدون پاساژ"} · {s.distance_km} کیلومتر
                  </p>
                </div>
                <div className="shrink-0 text-left">
                  <p className="num text-[13px] font-bold">{fa(s.arrival_time)}</p>
                  <p className="text-[9px] text-ink-300">زمان رسیدن</p>
                </div>
              </div>

              {s.price && <p className="num mt-1 text-[12px] text-ink-700">{money(s.price)}</p>}

              <div className="mt-1.5 flex flex-wrap gap-1">
                <span
                  className={`badge ${
                    s.open_state === "open"
                      ? "bg-brand-50 text-brand-700"
                      : s.open_state === "closed"
                        ? "bg-danger-50 text-danger-500"
                        : "bg-slate-100 text-ink-500"
                  }`}
                >
                  {s.open_state === "open"
                    ? `باز تا ${fa(s.closes_at)}`
                    : s.open_state === "closed"
                      ? "بسته در این ساعت"
                      : "ساعت نامشخص"}
                </span>
                {s.warning && (
                  <span className="badge bg-warn-50 text-warn-500">
                    <Icon name="warn" size={10} /> {s.warning}
                  </span>
                )}
              </div>

              {s.mall?.guide?.ask_sentence && (
                <p className="mt-1.5 rounded-lg bg-accent-400/10 px-2 py-1.5 text-[10px] leading-5 text-accent-600">
                  «{s.mall.guide.ask_sentence}»
                </p>
              )}
            </div>
          ))}

          <p className="pt-1 text-center text-[10px] text-ink-300">
            ترتیب بر اساس نزدیک‌ترین توقف است؛ ۲۰ دقیقه برای هر بازدید در نظر گرفته شده.
          </p>
        </div>
      )}
    </Screen>
  );
}
