"use client";

import { fa, money, priceRange } from "@/lib/format";
import { useApp } from "@/lib/store";
import { EmptyState, Icon, Screen } from "./ui";

export default function Saved() {
  const { state, back, go, set } = useApp();
  const { products, stores } = state.saved;

  return (
    <Screen title="ذخیره‌ها" subtitle={`${fa(products.length)} محصول · ${fa(stores.length)} فروشگاه`} onBack={back}>
      {products.length === 0 && stores.length === 0 && (
        <EmptyState
          icon="star"
          title="هنوز چیزی ذخیره نکرده‌اید"
          body="محصول‌ها و فروشگاه‌هایی که می‌خواهید بعداً ببینید اینجا نگه داشته می‌شوند."
          action={
            <button className="btn-soft" onClick={() => go("home")}>
              شروع جست‌وجو
            </button>
          }
        />
      )}

      {products.length > 0 && (
        <section className="mt-2">
          <h2 className="mb-2 px-1 text-[13px] font-bold">محصول‌ها</h2>
          <div className="space-y-2">
            {products.map((p) => (
              <div key={p.product_id} className="card flex items-center gap-3 p-2.5">
                <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-slate-50">
                  {p.image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.image} alt={p.title} className="h-14 w-14 object-contain" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-1 text-[12px] font-semibold">{p.title}</p>
                  <p className="num text-[11px] text-ink-500">{priceRange(p.price_min, p.price_max)}</p>
                </div>
                <button
                  className="rounded-lg p-2 text-brand-700"
                  onClick={() => {
                    set({ activeProduct: p });
                    go("stores");
                  }}
                >
                  <Icon name="arrow" size={18} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {stores.length > 0 && (
        <section className="mt-4">
          <h2 className="mb-2 px-1 text-[13px] font-bold">فروشگاه‌ها</h2>
          <div className="space-y-2">
            {stores.map((s) => (
              <div key={s.shop_id} className="card flex items-center gap-3 p-2.5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                  <Icon name="store" size={18} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] font-semibold">{s.name}</p>
                  <p className="text-[10px] text-ink-300">
                    {s.location_label || "—"} · {s.price_valid ? money(s.price) : "قیمت نامشخص"}
                  </p>
                </div>
                <button
                  className="rounded-lg p-2 text-brand-700"
                  onClick={() => {
                    set({ activeStore: s });
                    go("store");
                  }}
                >
                  <Icon name="arrow" size={18} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </Screen>
  );
}
