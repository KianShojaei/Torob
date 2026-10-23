import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Vazirmatn", "system-ui", "sans-serif"],
      },
      colors: {
        ink: {
          900: "#0b1220",
          700: "#243044",
          500: "#5a6884",
          300: "#9aa7bd",
        },
        brand: {
          50: "#eefbf6",
          100: "#d3f5e8",
          200: "#a8ead4",
          300: "#6fd8b8",
          400: "#36bf98",
          500: "#12a37e",
          600: "#0a8365",
          700: "#0a6852",
          800: "#0a5343",
          900: "#084439",
        },
        accent: {
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
        },
        danger: { 500: "#e5484d", 50: "#fef2f2" },
        warn: { 500: "#d97706", 50: "#fffbeb" },
      },
      borderRadius: { xl2: "1.25rem", xl3: "1.75rem" },
      boxShadow: {
        card: "0 1px 2px rgba(11,18,32,.04), 0 8px 24px -12px rgba(11,18,32,.18)",
        sheet: "0 -8px 40px -12px rgba(11,18,32,.28)",
      },
      keyframes: {
        slideUp: { "0%": { transform: "translateY(12px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        pop: { "0%": { transform: "scale(.96)", opacity: "0" }, "100%": { transform: "scale(1)", opacity: "1" } },
        shimmer: { "100%": { transform: "translateX(-100%)" } },
      },
      animation: {
        slideUp: "slideUp .28s cubic-bezier(.2,.8,.2,1) both",
        pop: "pop .2s ease-out both",
      },
    },
  },
  plugins: [],
};
export default config;
