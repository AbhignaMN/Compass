import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      colors: {
        canvas: "var(--bg-canvas)",
        surface: "var(--bg-surface)",
        "surface-muted": "var(--bg-surface-muted)",
        ink: "var(--text-primary)",
        "ink-muted": "var(--text-secondary)",
        accent: "var(--accent-primary)",
        "accent-warm": "var(--accent-warm)",
        "accent-gold": "var(--accent-gold)",
        "accent-leaf": "var(--accent-leaf)",
        hairline: "var(--border-hairline)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        glow: "var(--shadow-glow)",
      },
    },
  },
  plugins: [],
};

export default config;
