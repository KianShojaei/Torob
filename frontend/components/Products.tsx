"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { fa, moneyShort } from "@/lib/format";
import { useApp } from "@/lib/store";
import type { Product } from "@/lib/types";
import ProductCard from "./ProductCard";
import { EmptyState, Icon, Screen, Sheet, Toast } from "./ui";

const SORTS = [
  { value: "balanced", label: "پیشنهاد ما" },
  { value: "cheap", label: "ارزان‌ترین" },
  { value: "shops", label: "بیشترین فروشنده" },
];

export default function Products() {
  const { state, set, go, back } = useApp();
  const [sort, setSort] = useState("balanced");
  const [toast, setToast] = useState<string | null>(null);
  const [sheet, setSheet] = useState<Product | null>(null);

  const items = useMemo(() => {
    const list = [...state.products];
    if (sort === "cheap") list.sort((a, b) => (a.price_median || 1e18) - (b.price_median || 1e18));
    if (sort === "shops") list.sort((a, b) => b.shop_count - a.shop_count);
    return list;
  }, [state.products, sort]);

  const toggle = (id: string) => {
    const has = state.selectedProducts.includes(id);
    const next = has
      ? state.selectedProducts.filter((x) => x !== id)
      : [...state.selectedProducts, id].slice(0, 4);
    set({ selectedProducts: next });
  };

  const openStores = (p: Product) => {
    set({ activeProduct: p });
    go("stores");
  };

  return (
    <Screen
      title={state.query ? `«${state.query}»` : state.category || "نتایج"}
      subtitle={`${fa(items.length)} محصول · قیمت‌ها ثبت‌شده در دیتاست`}
      onBack={back}
      right={
        <button onClick={() => go("saved")} aria-label="ذخیره‌ها" className="rounded-full p-2 active:bg-slate-100">
          <Icon name="star" size={20} />
        </button>
      }
      bottom={
        state.selectedProducts.length >= 1 ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 text-[12px] text-ink-500">
              {fa(state.selectedProducts.length)} محصول انتخاب شده
            </div>
            <button
              disabled={state.selectedProducts.length < 2}
              onClick={() => go("compare-products")}
              className="btn-primary px-5 py-2.5 text-[13px]"
            >
              <Icon name="compare" size={16} />
              مقایسه
            </button>
          </div>
        ) : undefined
      }
    >
      <Toast text={toast} />

      <div className="flex gap-1.5 overflow-x-auto py-2 sheet-scroll">
        {SORTS.map((s) => (
          <button
            key={s.value}
            onClick={() => setSort(s.value)}
            data-on={sort === s.value}
            className="chip"
          >
            {s.label}
          </button>
        ))}
        <button className="chip" data-tone="muted" onClick={() => setToast("فیلترها در صفحه‌ی فروشگاه‌ها اعمال می‌شوند")}>
          <Icon name="filter" size={13} /> فیلتر
        </button>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="محصولی پیدا نشد"
          body="بودجه را بازتر کنم یا دسته‌ی نزدیک‌تری پیشنهاد بدهم؟"
          action={
            <button onClick={back} className="btn-soft">
              تغییر جست‌وجو
            </button>
          }
        />
      ) : (
        <div className="space-y-2.5">
          {items.map((p, i) => (
            <ProductCard
              key={p.product_id}
              product={p}
              index={i}
              selected={state.selectedProducts.includes(p.product_id)}
              onToggleCompare={() => toggle(p.product_id)}
              onOpen={() => openStores(p)}
              onSelect={() => setSheet(p)}
            />
          ))}
        </div>
      )}

      <Sheet open={!!sheet} onClose={() => setSheet(null)} title={sheet?.title}>
        {sheet && (
          <div className="space-y-3 pb-3">
            <div className="flex gap-3">
              <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-xl bg-slate-50">
                <img
                  src={sheet.image || ""}
                  alt={sheet.title}
                  className="h-24 w-24 rounded-xl object-contain"
                  onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                />
              </div>
              <div className="flex-1">
                <p className="num text-[18px] font-bold">{moneyShort(sheet.price_median)} تومان</p>
                <p className="mt-1 text-[11px] text-ink-500">
                  بازه‌ی بازار: {moneyShort(sheet.price_min)} تا {moneyShort(sheet.price_max)}
                </p>
                <p className="mt-1 text-[11px] text-ink-500">{fa(sheet.shop_count)} فروشگاه این محصول را دارند</p>
              </div>
            </div>

            <div>
              <h4 className="mb-1.5 text-[12px] font-bold">مشخصات کلیدی</h4>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(sheet.key_specs || {}).map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-slate-50 px-2.5 py-2">
                    <p className="text-[10px] text-ink-300">{k}</p>
                    <p className="text-[12px] font-medium">{v}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl bg-brand-50 p-3">
              <p className="mb-1 text-[11px] font-bold text-brand-800">چرا این مدل؟</p>
              <ul className="space-y-0.5">
                {(sheet.reasons || ["در دسته‌ی انتخابی شما و موجود در چند فروشگاه"]).slice(0, 3).map((r) => (
                  <li key={r} className="text-[11px] text-brand-700">• {r}</li>
                ))}
              </ul>
            </div>

            <div className="flex gap-2">
              <button className="btn-primary flex-1 py-2.5 text-[13px]" onClick={() => { set({ activeProduct: sheet }); setSheet(null); go("stores"); }}>
                فروشگاه‌های نزدیک
              </button>
              <button
                className="btn-ghost py-2.5 text-[13px]"
                onClick={() => {
                  toggle(sheet.product_id);
                  setSheet(null);
                }}
              >
                <Icon name="compare" size={15} /> مقایسه
              </button>
            </div>
          </div>
        )}
      </Sheet>
    </Screen>
  );
}
