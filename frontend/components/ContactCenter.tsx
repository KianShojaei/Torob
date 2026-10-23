"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { clock, fa, money, relativeSeconds } from "@/lib/format";
import { useApp } from "@/lib/store";
import type { ThreadStatus } from "@/lib/types";
import { DemoBadge, Icon, Screen, Toast } from "./ui";

const STATUS_META: Record<string, { label: string; tone: string; icon: any }> = {
  sent: { label: "ارسال شد", tone: "bg-slate-100 text-ink-500", icon: "arrow" },
  delivered: { label: "دیده شد", tone: "bg-slate-100 text-ink-500", icon: "arrow" },
  replied: { label: "پاسخ آمد", tone: "bg-brand-50 text-brand-700", icon: "chat" },
  confirmed: { label: "تأیید شد", tone: "bg-brand-600 text-white", icon: "check" },
  out_of_stock: { label: "ناموجود", tone: "bg-danger-50 text-danger-500", icon: "close" },
  needs_followup: { label: "نیاز به پیگیری", tone: "bg-warn-50 text-warn-500", icon: "warn" },
  no_reply: { label: "پاسخ نداد", tone: "bg-danger-50 text-danger-500", icon: "warn" },
};

export default function ContactCenter() {
  const { state, set, back, go } = useApp();
  const [thread, setThread] = useState<ThreadStatus | null>(
    state.activeThread ? state.threads[state.activeThread] || null : null,
  );
  const [toast, setToast] = useState<string | null>(null);
  const [alternatives, setAlternatives] = useState<any>(null);
  const [checkingAlt, setCheckingAlt] = useState(false);
  const timer = useRef<any>(null);

  const id = state.activeThread;

  useEffect(() => {
    if (!id) return;
    let stopped = false;

    const poll = async () => {
      try {
        const st = await api.contactStatus(id);
        if (stopped) return;
        setThread(st);
        set({ threads: { ...state.threads, [id]: st } });
        if (["confirmed", "out_of_stock", "no_reply", "needs_followup"].includes(st.status)) {
          clearInterval(timer.current);
          if (st.status === "no_reply" || st.status === "out_of_stock") {
            loadAlternatives(st);
          }
        }
      } catch {
        /* keep polling */
      }
    };

    poll();
    timer.current = setInterval(poll, 1500);
    return () => {
      stopped = true;
      clearInterval(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadAlternatives = async (st: ThreadStatus) => {
    if (!state.activeProduct) return;
    setCheckingAlt(true);
    try {
      const res = await api.alternatives({
        product_id: state.activeProduct.product_id,
        reason: st.status === "out_of_stock" ? "out_of_stock" : "no_reply",
        lat: state.location?.lat,
        lon: state.location?.lon,
        exclude_shop_ids: [st.shop_id],
        limit: 3,
      });
      setAlternatives(res);
    } finally {
      setCheckingAlt(false);
    }
  };

  const retailStore = state.stores.find((s) => s.shop_id === thread?.shop_id) || state.activeStore;

  return (
    <Screen
      title={retailStore?.name || "گفت‌وگو با فروشنده"}
      subtitle={thread ? STATUS_META[thread.status]?.label : "در حال ارسال"}
      onBack={back}
      right={<DemoBadge text="شبیه‌سازی" />}
    >
      <Toast text={toast} />

      {!thread && (
        <div className="mt-10 text-center text-[13px] text-ink-500">
          گفت‌وگویی انتخاب نشده است.
          <button className="mt-3 block w-full btn-soft" onClick={back}>
            بازگشت
          </button>
        </div>
      )}

      {thread && (
        <>
          {/* progress */}
          <div className="mt-2 card p-3">
            <div className="flex items-center justify-between">
              {["sent", "delivered", "replied"].map((step, i) => {
                const order = ["sent", "delivered", "replied", "confirmed"];
                const idx = order.indexOf(thread.status === "out_of_stock" || thread.status === "no_reply" ? "sent" : thread.status);
                const done = i <= (idx === -1 ? 0 : idx);
                return (
                  <div key={step} className="flex flex-1 items-center">
                    <div className="flex flex-col items-center gap-1">
                      <span
                        className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] ${
                          done ? "bg-brand-600 text-white" : "bg-slate-100 text-ink-300"
                        }`}
                      >
                        <Icon name={done ? "check" : "clock"} size={13} />
                      </span>
                      <span className="text-[9px] text-ink-500">
                        {step === "sent" ? "ارسال" : step === "delivered" ? "دیده شد" : "پاسخ"}
                      </span>
                    </div>
                    {i < 2 && <span className={`mx-1 h-0.5 flex-1 ${done ? "bg-brand-500" : "bg-slate-100"}`} />}
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
              <span className={`badge ${STATUS_META[thread.status]?.tone}`}>
                <Icon name={STATUS_META[thread.status]?.icon || "info"} size={11} />
                {STATUS_META[thread.status]?.label}
              </span>
              {thread.seconds_remaining != null && ["sent", "delivered"].includes(thread.status) && (
                <span className="num text-[11px] text-ink-500">
                  تا پایان فرصت: {relativeSeconds(thread.seconds_remaining)}
                </span>
              )}
              {thread.replied_at && (
                <span className="num text-[11px] text-ink-300">پاسخ {clock(thread.replied_at)}</span>
              )}
            </div>
          </div>

          {/* conversation */}
          <div className="mt-3 space-y-2">
            {thread.messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-start" : "justify-end"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-[12px] leading-6 ${
                    m.role === "user"
                      ? "bg-brand-600 text-white"
                      : m.role === "system"
                        ? "bg-slate-100 text-ink-500"
                        : "border border-slate-100 bg-white text-ink-900"
                  }`}
                >
                  {m.role === "seller" && (
                    <p className="mb-1 flex items-center gap-1 text-[9px] text-ink-300">
                      <Icon name="spark" size={10} /> پاسخ شبیه‌سازی‌شده
                    </p>
                  )}
                  {m.body}
                  <p className={`mt-1 text-[9px] ${m.role === "user" ? "text-white/60" : "text-ink-300"}`}>
                    {clock(m.created_at)}
                  </p>
                </div>
              </div>
            ))}
            {["sent", "delivered"].includes(thread.status) && (
              <div className="flex justify-end">
                <div className="flex gap-1 rounded-2xl border border-slate-100 bg-white px-3 py-2.5">
                  {[0, 1, 2].map((d) => (
                    <span
                      key={d}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300"
                      style={{ animationDelay: `${d * 120}ms` }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* parsed answer */}
          {thread.parsed && (
            <div className="mt-3 card p-3">
              <h3 className="mb-2 text-[12px] font-bold">خلاصه‌ی پاسخ فروشنده</h3>
              <div className="grid grid-cols-2 gap-1.5">
                <ParsedCell label="موجودی" value={thread.parsed.in_stock === true ? "موجود" : thread.parsed.in_stock === false ? "ناموجود" : "نامشخص"} />
                <ParsedCell label="قیمت تأییدشده" value={thread.parsed.confirmed_price ? money(thread.parsed.confirmed_price) : "نامشخص"} />
                <ParsedCell label="ساعت" value={thread.parsed.hours_info || "—"} />
                <ParsedCell label="نیاز به پیگیری" value={thread.parsed.needs_followup ? "بله" : "خیر"} />
              </div>
              <p className="mt-2 text-[10px] leading-4 text-ink-300">
                این مقادیر از متن پاسخ استخراج شده‌اند. قیمت ثبت‌شده در دیتاست تغییر نمی‌کند؛ فقط
                «تأیید فروشنده» به کارت اضافه می‌شود.
              </p>
            </div>
          )}

          {/* failover */}
          {(thread.status === "no_reply" || thread.status === "out_of_stock") && (
            <div className="mt-3 card overflow-hidden">
              <div className="flex items-start gap-2 bg-warn-50 p-3">
                <span className="mt-0.5 text-warn-500">
                  <Icon name="warn" size={16} />
                </span>
                <div>
                  <p className="text-[12px] font-bold text-warn-500">
                    {thread.status === "no_reply" ? "فروشنده پاسخ نداد" : "این مدل موجود نیست"}
                  </p>
                  <p className="mt-0.5 text-[11px] leading-5 text-ink-500">
                    جایگزین‌های نزدیک را آماده کرده‌ام تا خریدتان عقب نیفتد.
                  </p>
                </div>
              </div>

              {checkingAlt && <p className="p-3 text-[12px] text-ink-500">در حال پیدا کردن جایگزین…</p>}

              {alternatives?.same_product_elsewhere?.length > 0 && (
                <div className="space-y-1.5 p-3">
                  <p className="text-[11px] font-bold">همین محصول در فروشگاه‌های دیگر</p>
                  {alternatives.same_product_elsewhere.map((s: any) => (
                    <button
                      key={s.shop_id}
                      onClick={() => {
                        set({ activeStore: s });
                        go("store");
                      }}
                      className="flex w-full items-center justify-between rounded-xl border border-slate-100 px-2.5 py-2 text-right active:bg-slate-50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-[12px] font-medium">{s.name}</span>
                        <span className="text-[10px] text-ink-300">{s.distance_note}</span>
                      </span>
                      <span className="num shrink-0 text-[12px] font-bold">{money(s.price)}</span>
                    </button>
                  ))}
                </div>
              )}

              {alternatives?.similar_products?.length > 0 && (
                <div className="border-t border-slate-100 p-3">
                  <p className="mb-1.5 text-[11px] font-bold">
                    مدل‌های مشابه <span className="font-normal text-ink-300">(نه همان محصول)</span>
                  </p>
                  {alternatives.similar_products.slice(0, 3).map((p: any) => (
                    <button
                      key={p.product_id}
                      onClick={() => {
                        set({ activeProduct: p });
                        go("stores");
                      }}
                      className="mb-1 flex w-full items-center justify-between rounded-xl bg-slate-50 px-2.5 py-2 text-right"
                    >
                      <span className="line-clamp-1 text-[11px]">{p.title}</span>
                      <span className="num shrink-0 text-[11px] font-bold">{money(p.price_median)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* actions */}
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              className="btn-ghost py-2.5 text-[12px]"
              onClick={async () => {
                const t = await api.contact({
                  shop_id: thread.shop_id,
                  product_id: thread.product_id,
                  intent: "hours",
                  message: "سلام، تا چه ساعتی باز هستید؟",
                });
                set({ threads: { ...state.threads, [t.thread_id]: t }, activeThread: t.thread_id });
                setThread(t);
              }}
            >
              <Icon name="clock" size={15} /> پرسش ساعت کاری
            </button>
            <button
              className="btn-ghost py-2.5 text-[12px]"
              onClick={() => {
                if (retailStore) {
                  set({ activeStore: retailStore });
                  go("store");
                }
              }}
            >
              <Icon name="store" size={15} /> کارت فروشگاه
            </button>
          </div>

          <p className="mt-3 mb-2 text-center text-[10px] leading-4 text-ink-300">
            این گفت‌وگو شبیه‌سازی است. هیچ پیام واقعی برای فروشگاه ارسال نمی‌شود و شماره‌های دیتاست
            نمایشی‌اند.
          </p>
        </>
      )}
    </Screen>
  );
}

function ParsedCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-2.5 py-2">
      <p className="text-[9px] text-ink-300">{label}</p>
      <p className="mt-0.5 text-[11px] font-semibold">{value}</p>
    </div>
  );
}
