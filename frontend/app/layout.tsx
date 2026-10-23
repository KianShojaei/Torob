import type { Metadata, Viewport } from "next";
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "ترب‌گرد — دستیار خرید حضوری",
  description:
    "قبل از اینکه راه بیفتی مطمئن شو: انتخاب مدل، پیدا کردن فروشگاه نزدیک، تأیید قیمت و موجودی از فروشنده، و مسیر تا در مغازه.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "ترب‌گرد", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#0a8365",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
