"use client";

import { motion } from "framer-motion";

interface FitCompassDialProps {
  scorePct: number;
  label: "True North" | "Heading right" | "Detour";
}

export function FitCompassDial({ scorePct, label }: FitCompassDialProps) {
  // 100% -> 0 deg (pointing straight True North); lower scores deflect east up to ~95 deg
  const clamped = Math.max(0, Math.min(100, scorePct));
  const needleAngle = Math.round(((100 - clamped) / 100) * 95);

  const badgeTone =
    label === "True North"
      ? "bg-accent-leaf/15 text-accent-leaf border-accent-leaf/30"
      : label === "Heading right"
        ? "bg-accent-gold/15 text-accent-gold border-accent-gold/35"
        : "bg-accent-warm/15 text-accent-warm border-accent-warm/30";

  return (
    <div className="flex items-center gap-2.5">
      <div className="relative flex items-center justify-center" title={`${clamped}% match (${label})`}>
        <svg width="46" height="46" viewBox="0 0 60 60" className="compass-glow">
          <circle
            cx="30"
            cy="30"
            r="26"
            fill="var(--bg-surface-muted)"
            stroke="var(--border-brass)"
            strokeWidth="1.4"
          />
          {/* North marker */}
          <line x1="30" y1="5" x2="30" y2="10" stroke="var(--needle-north)" strokeWidth="2" />
          <line x1="55" y1="30" x2="50" y2="30" stroke="var(--text-secondary)" strokeOpacity="0.4" strokeWidth="1.2" />
          <line x1="30" y1="55" x2="30" y2="50" stroke="var(--text-secondary)" strokeOpacity="0.4" strokeWidth="1.2" />
          <line x1="5" y1="30" x2="10" y2="30" stroke="var(--text-secondary)" strokeOpacity="0.4" strokeWidth="1.2" />

          <motion.g
            style={{ originX: "30px", originY: "30px" }}
            initial={{ rotate: 75 }}
            animate={{ rotate: needleAngle }}
            transition={{ type: "spring", stiffness: 120, damping: 14 }}
          >
            <polygon points="30,11 33.2,30 26.8,30" fill="var(--needle-north)" />
            <polygon points="30,49 33.2,30 26.8,30" fill="var(--needle-south)" fillOpacity="0.7" />
            <circle cx="30" cy="30" r="2.8" fill="var(--bg-surface)" stroke="var(--accent-gold)" strokeWidth="1.4" />
          </motion.g>
        </svg>
      </div>
      <div className="flex flex-col">
        <span className="font-serif text-lg font-semibold leading-none text-ink">
          {clamped}%
        </span>
        <span
          className={`mt-1 inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide ${badgeTone}`}
        >
          {label}
        </span>
      </div>
    </div>
  );
}
