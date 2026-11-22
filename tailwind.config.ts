import type { Config } from "tailwindcss";

// Every color resolves to a CSS variable defined in src/app/globals.css,
// so the whole UI switches between the light "nude" and dark "earth" themes
// by toggling the `dark` class on <html>.
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;
const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;
const scale = (name: string) =>
  Object.fromEntries(STEPS.map((s) => [s, v(`${name}-${s}`)]));

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surfaces
        canvas: v("canvas"), // page background
        sunken: v("sunken"), // inputs, inset tiles
        surface: v("surface"), // cards, sidebar, panels
        raised: v("raised"), // nested blocks, chips
        highlight: v("highlight"), // hover state
        line: { DEFAULT: v("line"), strong: v("line-strong") },

        // Text
        ink: v("ink"), // primary text (flips with theme)
        "on-accent": v("on-accent"), // text on solid colored fills
        shade: v("shade"), // shadow tint

        // Brand solid (buttons, active nav)
        accent: { DEFAULT: v("accent"), hover: v("accent-hover"), deep: v("accent-deep") },

        // Families
        brand: scale("brand"), // olive & sage — growth, healthy
        water: scale("water"), // teal — irrigation, moisture
        sun: scale("sun"), // amber — solar, warnings
        clay: scale("clay"), // terracotta — energy, heat
        alert: scale("alert"), // brick — critical
        earth: scale("earth"), // warm neutrals

        // Text on glass: text-glass-title (#103C48) for titles & values, text-glass-label (#2B5B67) for labels
        glass: { title: v("glass-title"), label: v("glass-label") },

        black: "#14110D",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        arabic: ["var(--font-cairo)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        glass: "var(--radius-card)", // 24px — glass cards
        "glass-sm": "var(--radius-small)", // 16px — small glass elements
      },
      boxShadow: {
        glass: "var(--glass-shadow)",
        card: "var(--card-shadow)",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
        "in-out-soft": "cubic-bezier(0.65, 0, 0.35, 1)",
      },
      animation: {
        // Calm overrides: no bounce, no flashing, no fast pulses anywhere in the app.
        ping: "qa-soft-ping 3s cubic-bezier(0.22, 1, 0.36, 1) infinite",
        pulse: "qa-soft-pulse 3s cubic-bezier(0.65, 0, 0.35, 1) infinite",
        bounce: "qa-soft-pulse 2.4s cubic-bezier(0.65, 0, 0.35, 1) infinite",
        "pulse-subtle": "qa-soft-pulse 4s cubic-bezier(0.65, 0, 0.35, 1) infinite",
        "water-flow": "flow 3s linear infinite",
      },
      keyframes: {
        flow: {
          "0%": { strokeDashoffset: "24" },
          "100%": { strokeDashoffset: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
