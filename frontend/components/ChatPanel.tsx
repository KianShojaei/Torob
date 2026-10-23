"use client";

import { useEffect, useRef, useState } from "react";
import { streamAgent } from "@/lib/api";
import { useApp } from "@/lib/store";
import type { Product, Store } from "@/lib/types";
import { Icon } from "./ui";

const SUGGESTIONS = [
  "هدفون بلوتوثی زیر ۳ میلیون",
  "گوشی قسطی تا ۲۰ میلیون",
  "فروشگاه نزدیک برای یخچال ساید",
  "مقایسه دو مدل اول",
];

export default function ChatPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { state, set, go } = useApp();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toolTrace, setToolTrace] = useState<string[]>([]);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [state.messages, busy]);

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setInput("");
    const userMsg = { role: "user" as const, text };
    set({ messages: [...state.messages, userMsg] });
    setToolTrace([]);

    const cards: string[] = [];
    let answer = "";

    try {
      await streamAgent(
        {
          message: text,
          session_id: state.sessionId || undefined,
          lat: state.location?.lat,
          lon: state.location?.lon,
        },
        (ev) => {
          if (ev.type === "tool_status") {
            setToolTrace((t) => [...t.slice(-4), `${ev.name} · ${ev.status}`]);
          } else if (ev.type === "state_update" && ev.session_id) {
            set({ sessionId: ev.session_id });
          } else if (ev.type === "text_delta") {
            answer = ev.text;
          } else if (ev.type === "card") {
            cards.push(ev.card.kind);
            applyCard(ev.card.kind, ev.card.payload);
          } else if (ev.type === "done") {
            set({
              sessionId: ev.session_id,
              messages: [
                ...state.messages,
                userMsg,
                { role: "agent" as const, text: answer, degraded: ev.degraded, cards },
              ],
            });
          }
        },
      );
    } catch {
      set({
        messages: [
          ...state.messages,
          { role: "agent", text: "ارتباط با دستیار برقرار نشد. جست‌وجوی متنی همچنان کار می‌کند." },
        ],
      });
    } finally {
      setBusy(false);
    }
  };

  const applyCard = (kind: string, payload: any) => {
    if (kind === "product_list" && payload.products?.length) {
      set({ products: payload.products as Product[], activeProduct: payload.products[0] });
    }
    if (kind === "store_list" && payload.stores?.length) {
      set({ stores: payload.stores as Store[] });
    }
    if (kind === "contact_thread" && payload.thread_id) {
      set({ activeThread: payload.thread_id, threads: { ...state.threads, [payload.thread_id]: payload } });
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 mx-auto flex max-w-md flex-col bg-[#f6f8fb]">
      <header className="glass hairline flex items-center gap-2 px-3 py-3">
        <button aria-label="بستن" onClick={onClose} className="rounded-full p-2 active:bg-slate-100">
          <Icon name="close" size={20} />
        </button>
        <div className="flex-1">
          <h2 className="text-[15px] font-bold">دستیار خرید</h2>
          <p className="text-[10px] text-ink-500">
            {state.meta?.llm?.degraded ? "حالت قاعده‌محور (بدون مدل زبانی)" : "مدل زبانی فعال"}
          </p>
        </div>
        <span className="badge bg-brand-50 text-brand-700">
          <Icon name="spark" size={11} /> ایجنتیک
        </span>
      </header>

      <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto px-3 py-3 sheet-scroll">
        {state.messages.length === 0 && (
          <div className="mt-6 text-center">
            <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-3xl bg-brand-50 text-brand-700">
              <Icon name="spark" size={26} />
            </div>
            <p className="text-[13px] font-bold">چه چیزی می‌خواهید بخرید؟</p>
            <p className="mt-1 px-4 text-[11px] leading-5 text-ink-500">
              بگویید چه می‌خواهید و تا چه بودجه‌ای؛ من مدل‌ها را مقایسه می‌کنم، فروشگاه نزدیک را پیدا
              می‌کنم و قیمت و موجودی را از فروشنده می‌پرسم.
            </p>
            <div className="mt-4 space-y-1.5 px-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-right text-[12px] active:scale-[.99]"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {state.messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[86%] rounded-2xl px-3 py-2 text-[12.5px] leading-6 ${
                m.role === "user" ? "bg-brand-600 text-white" : "border border-slate-100 bg-white"
              }`}
            >
              {m.text}
              {m.role === "agent" && (m.cards?.length || m.degraded) && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {(m.cards || []).map((c) => (
                    <button
                      key={c}
                      onClick={() => openCard(c)}
                      className="rounded-lg bg-slate-50 px-2 py-1 text-[10px] text-ink-500"
                    >
                      {CARD_LABEL[c] || c}
                    </button>
                  ))}
                  {m.degraded && (
                    <span className="rounded-lg bg-slate-100 px-2 py-1 text-[10px] text-ink-300">
                      قاعده‌محور
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="flex justify-end">
            <div className="rounded-2xl border border-slate-100 bg-white px-3 py-2">
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map((d) => (
                  <span
                    key={d}
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-500"
                    style={{ animationDelay: `${d * 120}ms` }}
                  />
                ))}
                {toolTrace.length > 0 && (
                  <span className="num mr-1 text-[9px] text-ink-300">{toolTrace[toolTrace.length - 1]}</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 bg-white px-3 pb-[calc(10px+var(--safe-bottom))] pt-2">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={1}
            placeholder="مثلاً: هدفون بی‌سیم زیر ۲ میلیون، قسطی"
            className="max-h-24 min-h-[42px] flex-1 resize-none rounded-2xl border border-slate-200 px-3 py-2.5 text-[13px] outline-none focus:border-brand-500"
          />
          <button
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
            className="mb-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-600 text-white disabled:opacity-40"
          >
            <Icon name="arrow" size={19} className="rotate-180" />
          </button>
        </div>
      </div>
    </div>
  );

  function openCard(kind: string) {
    if (kind === "product_list") go("products");
    else if (kind === "store_list") go("stores");
    else if (kind === "contact_thread") go("contact");
    else if (kind === "visit_plan") go("plan");
    else if (kind === "store_compare") go("compare-stores");
    else if (kind === "product_compare") go("compare-products");
    onClose();
  }
}

const CARD_LABEL: Record<string, string> = {
  product_list: "مشاهده محصولات",
  product_compare: "جدول مقایسه",
  store_list: "فروشگاه‌ها",
  store_compare: "مقایسه فروشگاه",
  alternatives: "جایگزین‌ها",
  mall_guide: "راهنمای پاساژ",
  visit_plan: "برنامه سفر",
  contact_thread: "گفت‌وگو",
};
