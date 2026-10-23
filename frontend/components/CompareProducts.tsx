"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fa, moneyShort } from "@/lib/format";
import { useApp } from "@/lib/store";
import { Icon, Screen, Skeleton } from "./ui";

export default function CompareProducts() {
  const { state, back, go, set } = useApp();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (state.selectedProducts.length < 2) return;
    api
      .compareProducts(state.selectedProducts)
      .then((r) => setData(r))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [state.selectedProducts]);

  return (
    <Screen title="مقایسه‌ی محصولات" subtitle={`${fa(state.selectedProducts.length)} محصول`} onBack={back}>
      {loading && (
        <div className="space-y-2 pt-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-40" />
        </div>
      )}

      {data?.products && (
        <div className="space-y-3 pt-2">
          <div className="card overflow-hidden">
            <div className="grid" style={{ gridTemplateColumns: `repeat(${data.products.length}, minmax(0,1fr))` }}>
              {data.products.map((p: any) => (
                <div
                  key={p.product_id}
                  className={`relative border-l border-slate-100 p-2 text-center first:border-l-0 ${
                    p.is_cheapest ? "bg-brand-50/50" : ""
                  }`}
                >
                  {p.is_cheapest && (
                    <span className="absolute inset-x-1 top-1 rounded-md bg-brand-600 px-1 py-0.5 text-[9px] text-white">
                      ارزان‌ترین
                    </span>
                  )}
                  <img
                    src={p.image || ""}
                    alt={p.title}
                    className="mx-auto mt-4 h-16 w-16 rounded-lg object-contain"
                    onError={(e) => ((e.target as HTMLImageElement).style.opacity = "0")}
                  />
                  <p className="mt-1 line-clamp-3 text-[11px] font-semibold leading-4">{p.title}</p>
                  <p className="num mt-1 text-[12px] font-bold text-brand-700">{moneyShort(p.price_median)}</p>
                  <p className="text-[10px] text-ink-300">{fa(p.shop_count)} فروشگاه</p>
                </div>
              ))}
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="grid grid-cols-3 border-b border-slate-100 bg-slate-50 px-3 py-2 text-[11px] font-bold text-ink-500">
              <span>مشخصه</span>
              {data.products.map((p: any) => (
                <span key={p.product_id} className="truncate text-center">
                  {p.brand || "—"}
                </span>
              ))}
            </div>
            {data.spec_rows.length === 0 && (
              <p className="p-3 text-[12px] text-ink-500">
                مشخصات کلیدی برای این مدل‌ها ثبت نشده؛ فقط قیمت و تعداد فروشنده قابل مقایسه است.
              </p>
            )}
            {data.spec_rows.map((row: any) => {
              const values = Object.values(row.values) as string[];
              const allSame = new Set(values).size === 1;
              return (
                <div
                  key={row.spec}
                  className={`grid grid-cols-3 items-center border-b border-slate-50 px-3 py-2 text-[11px] ${
                    allSame ? "opacity-50" : ""
                  }`}
                >
                  <span className="text-ink-500">{row.spec}</span>
                  {data.products.map((p: any) => (
                    <span key={p.product_id} className="text-center font-medium">
                      {row.values[p.product_id] || "—"}
                    </span>
                  ))}
                </div>
              );
            })}
          </div>

          <div className="card p-3">
            <p className="mb-1 flex items-center gap-1 text-[11px] font-bold">
              <Icon name="info" size={13} /> درباره‌ی این مقایسه
            </p>
            <p className="text-[11px] leading-5 text-ink-500">
              مشخصات از فیلدهای ثبت‌شده‌ی محصول می‌آید و قیمت‌ها میانه‌ی فروشندگان فعلی است. سلول‌های
              خاکستری یعنی مقدار برای همه یکسان است.
            </p>
          </div>

          <button
            className="btn-primary w-full"
            onClick={() => {
              set({ activeProduct: data.products[0] as any });
              go("stores");
            }}
          >
            دیدن فروشگاه‌های ارزان‌ترین گزینه
            <Icon name="arrow" size={16} />
          </button>
        </div>
      )}
    </Screen>
  );
}
