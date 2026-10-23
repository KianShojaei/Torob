"use client";

import { fa, distance } from "@/lib/format";
import type { Store } from "@/lib/types";
import { AvailabilityBadge, Icon, InstallmentBadge, OpenBadge, PriceBlock } from "./ui";

export default function StoreCard({
  store,
  onOpen,
  onContact,
  onCompare,
  inCompare,
  onShowGuide,
  compact = false,
}: {
  store: Store;
  onOpen?: () => void;
  onContact?: () => void;
  onCompare?: () => void;
  inCompare?: boolean;
  onShowGuide?: () => void;
  compact?: boolean;
}) {
  const closedOnArrival = store.open_on_arrival === "closed";
  return (
    <article
      className={`card overflow-hidden ${closedOnArrival ? "opacity-95" : ""}`}
      onClick={onOpen}
    >
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h3 className="truncate text-[15px] font-bold">{store.name}</h3>
              {store.name_is_real && (
                <span title="هویت واقعی ثبت‌شده" className="text-brand-600">
                  <Icon name="shield" size={13} />
                </span>
              )}
            </div>
            <p className="mt-0.5 flex items-center gap-1 text-[12px] text-ink-500">
              <Icon name="pin" size={12} />
              {store.location_label || "محله نامشخص"}
              {store.mall.name && <> · {store.mall.name}</>}
            </p>
          </div>
          <div className="shrink-0 text-left">
            <p className="num text-[12px] font-semibold text-ink-700">
              {distance(store.distance_km, store.travel_minutes)}
            </p>
            {store.distance_km >= 0 && (
              <p className="text-[10px] text-ink-300">
                {store.mode === "walk" ? "پیاده" : "با ماشین"}
              </p>
            )}
          </div>
        </div>

        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <OpenBadge
            state={store.open_state}
            opensAt={store.opens_at}
            closesAt={store.closes_at}
            onArrival={store.open_on_arrival}
          />
          <AvailabilityBadge
            availability={store.availability}
            source={store.availability_source}
            at={store.availability_at}
          />
          <InstallmentBadge confirmed={store.installment_confirmed} declared={store.installment_declared} />
        </div>

        <div className="mt-3 flex items-end justify-between gap-2">
          <PriceBlock
            price={store.price}
            valid={store.price_valid}
            ageBucket={store.price_age_bucket}
            ageDays={store.price_age_days}
            market={store.market_position}
            size="md"
          />
          {store.score > 0 && (
            <div className="shrink-0 text-left">
              <div className="num text-[15px] font-bold text-brand-700">
                {fa(Math.round(store.score * 100))}
              </div>
              <div className="text-[10px] text-ink-300">امتیاز تطابق</div>
            </div>
          )}
        </div>

        {store.reasons.length > 0 && (
          <ul className="mt-2 space-y-1">
            {store.reasons.slice(0, compact ? 1 : 2).map((r) => (
              <li key={r} className="flex items-start gap-1 text-[11px] text-ink-500">
                <span className="mt-0.5 text-brand-600">
                  <Icon name="check" size={11} />
                </span>
                {r}
              </li>
            ))}
          </ul>
        )}

        {store.flags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {store.flags.map((f) => (
              <span key={f} className="badge bg-warn-50 text-warn-500">
                <Icon name="warn" size={10} /> {f}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-4 gap-px border-t border-slate-100 bg-slate-100">
        <ActionButton icon="chat" label="پرسش" onClick={onContact} primary />
        <ActionButton icon="route" label="مسیر" onClick={onShowGuide} />
        <ActionButton
          icon="compare"
          label={inCompare ? "در مقایسه" : "مقایسه"}
          onClick={onCompare}
          active={inCompare}
        />
        <ActionButton icon="store" label="جزئیات" onClick={onOpen} />
      </div>
    </article>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
  primary,
  active,
}: {
  icon: "chat" | "route" | "compare" | "store";
  label: string;
  onClick?: () => void;
  primary?: boolean;
  active?: boolean;
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      className={`flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition active:bg-slate-50 ${
        primary ? "text-brand-700" : active ? "text-accent-600" : "text-ink-500"
      } bg-white`}
    >
      <Icon name={icon} size={17} />
      {label}
    </button>
  );
}
