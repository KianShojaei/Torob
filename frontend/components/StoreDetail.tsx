"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { distance, fa, money, clock } from "@/lib/format";
import { useApp } from "@/lib/store";
import { AvailabilityBadge, Icon, InstallmentBadge, OpenBadge, PriceBlock, Screen, Sheet, Skeleton, Toast } from "./ui";

export default function StoreDetail() {
  const { state, back, go, set } = useApp();
  const store = state.activeStore;
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [hoursOpen, setHoursOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!store) return;
    api
      .shop(store.shop_id, state.location?.lat, state.location?.lon)
      .then(setDetail)
      .catch(() => setToast("جزئیات فروشگاه دریافت نشد"))
      .finally(() => setLoading(false));
  }, [store, state.location?.lat, state.location?.lon]);

  if (!store) {
    return (
      <Screen title="فروشگاه" onBack={back}>
        <p className="pt-6 text-center text-[13px] text-ink-500">فروشگاهی انتخاب نشده است.</p>
      </Screen>
    );
  }

  const guide = detail?.mall?.guide || store.mall.guide;
  const address = detail?.address || "";
  const phone = detail?.contacts?.[0]?.display_number;

  const contact = async (intent: string) => {
    try {
      const t = await api.contact({
        shop_id: store.shop_id,
        product_id: state.activeProduct?.product_id,
        intent,
      });
      set({ threads: { ...state.threads, [t.thread_id]: t }, activeThread: t.thread_id });
      go("contact");
    } catch {
      setToast("ارسال پیام ناموفق بود");
    }
  };

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(
        `${store.name} — ${guide?.title || address}${phone ? ` — ${phone}` : ""}`,
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setToast("کپی ممکن نشد");
    }
  };

  return (
    <Screen
      title={store.name}
      subtitle={`${store.location_label || ""} · ${distance(store.distance_km, store.travel_minutes)}`}
      onBack={back}
      right={
        <button
          aria-label="ذخیره"
          onClick={() => set({ saved: { ...state.saved, stores: [...state.saved.stores.filter((s) => s.shop_id !== store.shop_id), store] } })}
          className="rounded-full p-2 active:bg-slate-100"
        >
          <Icon name="star" filled={state.saved.stores.some((s) => s.shop_id === store.shop_id)} size={20} />
        </button>
      }
      bottom={
        <div className="flex gap-2">
          <button className="btn-primary flex-1 py-2.5 text-[13px]" onClick={() => contact("price_stock")}>
            <Icon name="chat" size={16} />
            پرسش قیمت و موجودی
          </button>
          <a
            className="btn-ghost py-2.5 text-[13px]"
            href={`https://www.google.com/maps/dir/?api=1&destination=${detail?.lat ?? store.lat},${
              detail?.lon ?? store.lon
            }`}
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="route" size={16} />
            مسیر
          </a>
        </div>
      }
    >
      <Toast text={toast} />

      {/* status strip */}
      <div className="mt-2 card p-3">
        <div className="flex flex-wrap gap-1.5">
          <OpenBadge state={store.open_state} opensAt={store.opens_at} closesAt={store.closes_at} onArrival={store.open_on_arrival} />
          <AvailabilityBadge availability={store.availability} />
          <InstallmentBadge confirmed={store.installment_confirmed} declared={store.installment_declared} />
          {detail?.fast_delivery === "true" && (
            <span className="badge bg-brand-50 text-brand-700">ارسال فوری</span>
          )}
        </div>
        <div className="mt-3">
          <PriceBlock
            price={store.price}
            valid={store.price_valid}
            ageBucket={store.price_age_bucket}
            ageDays={store.price_age_days}
            market={store.market_position}
            size="lg"
          />
        </div>
        {store.price && state.activeProduct?.price_median && (
          <p className="mt-1 text-[11px] text-ink-500">
            میانه‌ی بازار این محصول: <span className="num">{money(state.activeProduct.price_median)}</span>
          </p>
        )}
      </div>

      {/* in-mall guide */}
      <section className="mt-3 card overflow-hidden">
        <div className="flex items-center justify-between px-3 pt-3">
          <h3 className="flex items-center gap-1.5 text-[13px] font-bold">
            <Icon name="pin" size={15} /> راهنمای پیدا کردن مغازه
          </h3>
          <span className="badge bg-slate-100 text-ink-500">
            اطمینان {fa(Math.round((guide?.confidence || 0) * 100))}٪
          </span>
        </div>
        <div className="px-3 pb-3 pt-2">
          {loading ? (
            <Skeleton className="h-16" />
          ) : (
            <>
              <p className="text-[14px] font-semibold">{guide?.title || "آدرس ثبت نشده"}</p>
              <p className="mt-1 text-[12px] leading-6 text-ink-500">{guide?.detail}</p>

              {guide?.ask_sentence && (
                <div className="mt-2 rounded-xl bg-accent-400/10 p-2.5">
                  <p className="mb-1 text-[10px] font-bold text-accent-600">این جمله را از نگهبان بپرسید:</p>
                  <p className="text-[12px] leading-6">«{guide.ask_sentence}»</p>
                </div>
              )}

              {(guide?.missing || []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {guide.missing.map((m: string) => (
                    <span key={m} className="badge bg-slate-100 text-ink-500">
                      {m}: نامشخص
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-2 flex gap-2">
                <button onClick={copyAddress} className="btn-ghost flex-1 py-2 text-[12px]">
                  <Icon name="link" size={14} />
                  {copied ? "کپی شد" : "کپی آدرس"}
                </button>
                <button onClick={() => setHoursOpen(true)} className="btn-ghost flex-1 py-2 text-[12px]">
                  <Icon name="clock" size={14} />
                  ساعت کاری
                </button>
              </div>
            </>
          )}
        </div>
      </section>

      {/* address + contact */}
      <section className="mt-3 card p-3">
        <h3 className="mb-1.5 text-[13px] font-bold">آدرس و تماس</h3>
        <p className="text-[12px] leading-6 text-ink-700">{address || "آدرس ثبت نشده"}</p>
        {detail?.contacts?.length > 0 && (
          <div className="mt-2 flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="num text-[13px]" dir="ltr">
              {detail.contacts[0].display_number}
            </span>
            <span className="badge bg-warn-50 text-warn-500">شماره‌ی نمایشی</span>
          </div>
        )}
        {detail?.instagram && (
          <a href={detail.instagram} target="_blank" rel="noreferrer" className="mt-1.5 block text-[12px] text-brand-700 underline">
            اینستاگرام فروشگاه
          </a>
        )}
        {detail?.website && (
          <a href={detail.website} target="_blank" rel="noreferrer" className="mt-1 block text-[12px] text-brand-700 underline">
            وب‌سایت فروشگاه
          </a>
        )}
        <p className="mt-2 flex items-start gap-1 text-[10px] leading-4 text-ink-300">
          <Icon name="info" size={11} className="mt-0.5 shrink-0" />
          شماره‌ها در دیتاست نمایشی‌اند؛ تماس واقعی برقرار نمی‌شود. پاسخ فروشنده شبیه‌سازی شده است.
        </p>
      </section>

      {/* why suggested */}
      <section className="mt-3 card p-3">
        <h3 className="mb-2 text-[13px] font-bold">چرا این فروشگاه پیشنهاد شد؟</h3>
        <div className="space-y-1.5">
          {Object.entries(store.score_breakdown || {})
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([k, v]) => (
              <div key={k} className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-[10px] text-ink-500">{LABELS[k] || k}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <span className="block h-full rounded-full bg-brand-500" style={{ width: `${Math.round(v * 100)}%` }} />
                </span>
                <span className="num w-8 text-[10px] text-ink-300">{fa(Math.round(v * 100))}</span>
              </div>
            ))}
        </div>
      </section>

      {/* other products */}
      {detail?.offers?.length > 0 && (
        <section className="mt-3 card p-3">
          <h3 className="mb-2 text-[13px] font-bold">چند محصول دیگر همین فروشگاه</h3>
          <div className="space-y-1.5">
            {detail.offers.slice(0, 5).map((o: any) => (
              <div key={o.product_id} className="flex items-center justify-between gap-2 rounded-xl bg-slate-50 px-2.5 py-2">
                <span className="line-clamp-1 text-[11px]">{o.title}</span>
                <span className="num shrink-0 text-[11px] font-semibold">
                  {o.price_valid ? money(o.price) : "نامشخص"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <Sheet open={hoursOpen} onClose={() => setHoursOpen(false)} title="ساعت کاری هفته">
        {!detail?.hours_known ? (
          <p className="py-4 text-center text-[12px] text-ink-500">
            ساعت کاری این فروشگاه ثبت نشده است. «نامشخص» یعنی نمی‌دانیم؛ نه اینکه تعطیل است.
          </p>
        ) : (
          <div className="space-y-1 pb-2">
            {detail.hours.map((h: any) => (
              <div key={h.day} className="flex items-center justify-between rounded-lg px-2 py-1.5 odd:bg-slate-50">
                <span className="text-[12px]">{h.day}</span>
                <span className={`num text-[12px] ${h.known ? "" : "text-ink-300"}`}>{h.text}</span>
              </div>
            ))}
            <p className="pt-2 text-[10px] text-ink-300">
              اوقات شرعی و تعطیلات رسمی در محاسبه نیست. زمان‌ها به وقت تهران است.
            </p>
          </div>
        )}
      </Sheet>
    </Screen>
  );
}

const LABELS: Record<string, string> = {
  price: "قیمت",
  distance: "فاصله",
  open: "باز بودن",
  arrival: "زمان رسیدن",
  freshness: "تازگی قیمت",
  confirmation: "تأیید",
  installment: "اقساط",
  warranty: "گارانتی",
  confidence: "اطمینان آدرس",
};
