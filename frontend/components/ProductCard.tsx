"use client";

import { useState } from "react";
import { fa, priceRange } from "@/lib/format";
import type { Product } from "@/lib/types";
import { Icon } from "./ui";

export function ProductImage({
  src,
  alt,
  size = 96,
  className = "",
}: {
  src?: string | null;
  alt: string;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div
        className={`flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 text-slate-300 ${className}`}
        style={{ width: size, height: size }}
        aria-label="بدون تصویر"
      >
        <Icon name="store" size={Math.round(size / 3)} />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`shrink-0 rounded-xl bg-slate-50 object-contain ${className}`}
      style={{ width: size, height: size }}
    />
  );
}

export default function ProductCard({
  product,
  selected,
  onSelect,
  onToggleCompare,
  onOpen,
  index,
}: {
  product: Product;
  selected?: boolean;
  onSelect?: () => void;
  onToggleCompare?: () => void;
  onOpen?: () => void;
  index?: number;
}) {
  return (
    <article
      className={`card animate-slideUp p-3 transition ${
        selected ? "ring-2 ring-brand-600" : ""
      }`}
      style={{ animationDelay: `${Math.min((index || 0) * 40, 200)}ms` }}
      onClick={onSelect}
    >
      <div className="flex gap-3">
        <ProductImage src={product.image} alt={product.title} size={92} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="line-clamp-2 text-[14px] font-semibold leading-6">{product.title}</h3>
            {onToggleCompare && (
              <button
                aria-label="افزودن به مقایسه"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleCompare();
                }}
                className={`shrink-0 rounded-xl border p-1.5 ${
                  selected ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-200 text-ink-300"
                }`}
              >
                <Icon name="compare" size={15} />
              </button>
            )}
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {product.brand && (
              <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] text-ink-500">
                {product.brand}
              </span>
            )}
            {(product.badges || []).slice(0, 2).map((b) => (
              <span key={b} className="rounded-md bg-brand-50 px-1.5 py-0.5 text-[11px] text-brand-700">
                {b}
              </span>
            ))}
          </div>

          <div className="mt-2 flex items-end justify-between">
            <div>
              <p className="num text-[16px] font-bold">{priceRange(product.price_min, product.price_max)}</p>
              <p className="mt-0.5 text-[11px] text-ink-500">
                میانه‌ی بازار: <span className="num">{priceRange(product.price_median, product.price_median)}</span>
              </p>
            </div>
            <span className="badge bg-slate-100 text-ink-500">
              <Icon name="store" size={11} />
              {fa(product.shop_count)} فروشگاه
            </span>
          </div>
        </div>
      </div>

      {(product.reasons || []).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1 border-t border-dashed border-slate-100 pt-2">
          {(product.reasons || []).slice(0, 2).map((r) => (
            <span key={r} className="text-[11px] text-ink-500">
              <span className="text-brand-600">‹</span> {r}
            </span>
          ))}
        </div>
      )}

      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(product.key_specs || {})
          .slice(0, 3)
          .map(([k, v]) => (
            <span key={k} className="rounded-lg bg-slate-50 px-2 py-1 text-[11px] text-ink-500">
              {k}: <span className="font-medium text-ink-700">{v}</span>
            </span>
          ))}
      </div>

      {onOpen && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onOpen();
          }}
          className="mt-3 flex w-full items-center justify-center gap-1 rounded-xl bg-brand-50 py-2 text-[13px] font-semibold text-brand-700 active:scale-[.99]"
        >
          دیدن فروشنده‌های نزدیک
          <Icon name="arrow" size={15} />
        </button>
      )}
    </article>
  );
}
