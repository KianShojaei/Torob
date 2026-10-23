"use client";

import { useEffect, useState } from "react";
import { useApp } from "@/lib/store";
import ChatPanel from "./ChatPanel";
import CompareProducts from "./CompareProducts";
import CompareStores from "./CompareStores";
import ContactCenter from "./ContactCenter";
import Home from "./Home";
import Plan from "./Plan";
import Products from "./Products";
import Saved from "./Saved";
import StoreDetail from "./StoreDetail";
import Stores from "./Stores";
import { Icon } from "./ui";

export default function Shell() {
  const { state, go, back } = useApp();
  const [chat, setChat] = useState(false);

  // offline shell
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return;
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);

  useEffect(() => {
    document.documentElement.dir = "rtl";
  }, []);

  const views: Record<string, React.ReactNode> = {
    home: <Home />,
    products: <Products />,
    stores: <Stores />,
    store: <StoreDetail />,
    "compare-products": <CompareProducts />,
    "compare-stores": <CompareStores />,
    contact: <ContactCenter />,
    plan: <Plan />,
    saved: <Saved />,
  };

  const mainViews = new Set(["home", "products", "stores", "plan", "saved"]);
  const showNav = mainViews.has(state.view) && !chat;

  return (
    <>
      {views[state.view] || <Home />}

      {showNav && (
        <nav className="fixed inset-x-0 bottom-0 z-30 mx-auto max-w-md">
          <div className="glass border-t border-slate-200 pb-[calc(6px+var(--safe-bottom))] pt-1.5">
            <div className="relative flex items-center justify-around">
              <NavItem icon="home" label="خانه" active={state.view === "home"} onClick={() => go("home")} />
              <NavItem icon="cart" label="نتایج" active={state.view === "products"} onClick={() => (state.products.length ? go("products") : go("home"))} />
              <button
                onClick={() => setChat(true)}
                className="-mt-6 flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-[0_10px_24px_-8px_rgba(10,131,101,.9)] active:scale-95"
                aria-label="دستیار"
              >
                <Icon name="spark" size={24} />
              </button>
              <NavItem icon="store" label="فروشگاه" active={state.view === "stores"} onClick={() => (state.activeProduct ? go("stores") : go("home"))} />
              <NavItem icon="route" label="سفر" active={state.view === "plan"} onClick={() => go("plan")} />
            </div>
          </div>
        </nav>
      )}

      <ChatPanel open={chat} onClose={() => setChat(false)} />
    </>
  );
}

function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: any;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-16 flex-col items-center gap-0.5 py-1 text-[10px] ${
        active ? "text-brand-700" : "text-ink-300"
      }`}
    >
      <Icon name={icon} size={21} />
      {label}
    </button>
  );
}
