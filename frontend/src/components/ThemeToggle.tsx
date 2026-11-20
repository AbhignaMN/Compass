"use client";

import { motion } from "framer-motion";
import { Compass, Moon, Sun, Trees } from "lucide-react";
import { useState } from "react";

import type { ThemeId } from "@/lib/types";

interface ThemeToggleProps {
  theme: ThemeId;
  onChange: (theme: ThemeId) => void;
}

const THEMES: { id: ThemeId; label: string; swatch: string; desc: string }[] = [
  { id: "colourful", label: "Colourful", swatch: "#0e7c7b", desc: "Warm parchment & coastal tones" },
  { id: "midnight", label: "Midnight", swatch: "#0b1426", desc: "Deep navy & brass gold" },
  { id: "mahogany", label: "Mahogany", swatch: "#3d2419", desc: "Dark leather & burnished gold" },
];

export function ThemeToggle({ theme, onChange }: ThemeToggleProps) {
  const [open, setOpen] = useState(false);

  const iconFor = (id: ThemeId) => {
    if (id === "colourful") return <Sun className="h-4 w-4 text-accent-gold" />;
    if (id === "midnight") return <Moon className="h-4 w-4 text-accent-gold" />;
    return <Trees className="h-4 w-4 text-accent-gold" />;
  };

  const needleDeg = theme === "colourful" ? 0 : theme === "midnight" ? 120 : 240;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Switch Compass theme"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1.5 text-xs font-medium text-ink shadow-sm transition hover:border-accent-gold focus:outline-none focus:ring-2 focus:ring-accent-gold/50"
      >
        <motion.span
          animate={{ rotate: needleDeg }}
          transition={{ type: "spring", stiffness: 200, damping: 18 }}
          className="inline-flex"
        >
          <Compass className="h-4 w-4 text-accent" />
        </motion.span>
        <span className="hidden sm:inline capitalize">{theme}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.16 }}
            className="absolute right-0 z-40 mt-2 w-60 rounded-2xl border border-hairline bg-surface p-2 shadow-card"
            role="menu"
          >
            <p className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-widest text-ink-muted">
              Compass Palette
            </p>
            {THEMES.map((item) => {
              const active = theme === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={active}
                  onClick={() => {
                    onChange(item.id);
                    setOpen(false);
                  }}
                  className={`mt-1 flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition ${
                    active
                      ? "bg-surface-muted ring-1 ring-accent-gold/60"
                      : "hover:bg-surface-muted/70"
                  }`}
                >
                  <span
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-hairline"
                    style={{ backgroundColor: item.swatch }}
                  >
                    {iconFor(item.id)}
                  </span>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-ink">{item.label}</div>
                    <div className="truncate text-[11px] text-ink-muted">{item.desc}</div>
                  </div>
                </button>
              );
            })}
          </motion.div>
        </>
      )}
    </div>
  );
}
