"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { distance, fa, money } from "@/lib/format";
import { useApp } from "@/lib/store";
import { AvailabilityBadge, Icon, InstallmentBadge, OpenBadge, Screen, Skeleton } from "./ui";

export default function CompareStores() {
  const { state, back, go, set } = useApp();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!state.activeProduct || state.compareStores.length < 2) {
      setRows(state.compareStores);
      setLoading(false);
      return;
    }
    api
      .compareStores({
        product_id: state.activeProduct.product_id,
        shop_ids: state.compareStores.map((s) => s.shop_id),
        lat: state.location?.lat,
        lon: state.location?.lon,
      })
      .then((r) => setRows(r.rows))
      .catch(() => setRows(state.compareStores))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Screen
      title="مقایسه‌ی فروشگاه‌ها"
      subtitle={state.activeProduct?.title}
      onBack={back}
      bottom={
        <button className="btn-primary w-full py-2.5 text-[13px]" onClick={() => go("plan")}>
          <Icon name="route" size={16} /> ساخت برنامه‌ی سفر
        </button>
      }
    >
      {loading ? (
        <Skeleton className="mt-3 h-64" />
      ) : (
        <>
          <div className="mt-2 card overflow-hidden">
            <div className="grid grid-cols-5 border-b border-slate-100 bg-slate-50 px-2 py-2 text-[10px] font-bold text-ink-500">
              <span className="col-span-2">فروشگاه</span>
              <span className="text-center">قیمت</span>
              <span className="text-center">فاصله</span>
              <span className="text-center">ساعت</span>
            </div>
            {rows.map((r: any) => (
              <div key={r.shop_id} className="grid grid-cols-5 items-center border-b border-slate-50 px-2 py-2.5">
                <div className="col-span-2 min-w-0">
                  <p className="truncate text-[11px] font-semibold">{r.name}</p>
                  <p className="truncate text-[9px] text-ink-300">{r.location_label || "—"}</p>
                  {r.is_cheapest && <span className="badge mt-1 bg-brand-50 text-brand-700">ارزان‌ترین</span>}
                  {r.is_nearest && <span className="badge mt-1 bg-slate-100 text-ink-500">نزدیک‌ترین</span>}
                </div>
                <div className="text-center">
                  <p className="num text-[11px] font-bold">{r.price_valid ? money(r.price) : "نامشخص"}</p>
                  <p className="text-[9px] text-ink-300">{r.price_age_label}</p>
                </div>
                <div className="text-center">
                  <p className="num text-[10px]">{distance(r.distance_km, r.travel_minutes)}</p>
                </div>
                <div className="flex flex-col items-center gap-0.5">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      r.open_state === "open" ? "bg-brand-600" : r.open_state === "closed" ? "bg-danger-500" : "bg-slate-300"
                    }`}
                  />
                  <span className="text-[9px] text-ink-300">
                    {r.open_state === "open" ? r.closes_at : r.open_state === "closed" ? "بسته" : "نامشخص"}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 space-y-2">
            {rows.map((r: any) => (
              <div key={r.shop_id} className="card p-3">
                <div className="flex items-center justify-between">
                  <h3 className="truncate text-[13px] font-bold">{r.name}</h3>
                  <button
                    className="text-[11px] text-brand-700"
                    onClick={() => {
                      set({ activeStore: r });
                      go("store");
                    }}
                  >
                    جزئیات
                  </button>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  <OpenBadge state={r.open_state} opensAt={r.opens_at} closesAt={r.closes_at} onArrival={r.open_on_arrival} />
                  <AvailabilityBadge availability={r.availability} />
                  <InstallmentBadge confirmed={r.installment_confirmed} declared={r.installment_declared} />
                </div>
                {r.flags?.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {r.flags.map((f: string) => (
                      <span key={f} className="badge bg-warn-50 text-warn-500">
                        <Icon name="warn" size={10} /> {f}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-ink-300">
                  <span>امتیاز: {fa(Math.round((r.score || 0) * 100))}</span>
                  <span>ارزش‌گذاری بر اساس: قیمت، فاصله، ساعت، اقساط، تازگی</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </Screen>
  );
}
