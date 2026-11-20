"use client";

import { motion } from "framer-motion";

interface CompassRoseProps {
  size?: number;
  thinking?: boolean;
  className?: string;
  decorative?: boolean;
}

export function CompassRose({
  size = 40,
  thinking = false,
  className = "",
  decorative = false,
}: CompassRoseProps) {
  const ticks = Array.from({ length: 36 }, (_, i) => i * 10);

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      aria-hidden={decorative ? "true" : undefined}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "Compass rose"}
      className={`compass-glow shrink-0 ${className}`}
    >
      {/* Outer hairline brass bezel */}
      <circle
        cx="60"
        cy="60"
        r="55"
        stroke="var(--accent-gold)"
        strokeWidth="1.4"
        strokeOpacity="0.85"
      />
      <circle
        cx="60"
        cy="60"
        r="49"
        stroke="var(--border-brass)"
        strokeWidth="0.9"
      />

      {/* Fine degree tick ring */}
      {ticks.map((deg) => {
        const isCardinal = deg % 90 === 0;
        const isMajor = deg % 30 === 0;
        const inner = isCardinal ? 41 : isMajor ? 44 : 46.5;
        return (
          <line
            key={deg}
            x1="60"
            y1={60 - 49}
            x2="60"
            y2={60 - inner}
            stroke={isCardinal ? "var(--accent-gold)" : "var(--text-secondary)"}
            strokeOpacity={isCardinal ? 0.95 : isMajor ? 0.55 : 0.3}
            strokeWidth={isCardinal ? 1.8 : 1}
            transform={`rotate(${deg} 60 60)`}
          />
        );
      })}

      {/* Cardinal letters */}
      <text
        x="60"
        y="25"
        textAnchor="middle"
        fill="var(--needle-north)"
        fontSize="9.5"
        fontWeight="700"
        fontFamily="var(--font-fraunces), serif"
      >
        N
      </text>
      <text
        x="96"
        y="63"
        textAnchor="middle"
        fill="var(--text-secondary)"
        fontSize="8"
        fontWeight="600"
      >
        E
      </text>
      <text
        x="60"
        y="101"
        textAnchor="middle"
        fill="var(--text-secondary)"
        fontSize="8"
        fontWeight="600"
      >
        S
      </text>
      <text
        x="24"
        y="63"
        textAnchor="middle"
        fill="var(--text-secondary)"
        fontSize="8"
        fontWeight="600"
      >
        W
      </text>

      {/* Subtle 4-point inner star */}
      <path
        d="M60 32 L64 56 L88 60 L64 64 L60 88 L56 64 L32 60 L56 56 Z"
        fill="var(--accent-gold)"
        fillOpacity="0.14"
        stroke="var(--accent-gold)"
        strokeOpacity="0.4"
        strokeWidth="0.7"
      />

      {/* Animated compass needle */}
      <motion.g
        style={{ originX: "60px", originY: "60px" }}
        animate={
          thinking
            ? { rotate: [-28, 34, -14, 18, -5, 0] }
            : { rotate: [0, 3, -2, 0] }
        }
        transition={
          thinking
            ? { duration: 1.9, repeat: Infinity, ease: "easeInOut" }
            : { duration: 6, repeat: Infinity, ease: "easeInOut" }
        }
      >
        {/* North needle */}
        <polygon points="60,26 65,60 55,60" fill="var(--needle-north)" />
        {/* South needle */}
        <polygon points="60,94 65,60 55,60" fill="var(--needle-south)" fillOpacity="0.88" />
        {/* Brass center pivot */}
        <circle cx="60" cy="60" r="4.5" fill="var(--bg-surface)" stroke="var(--accent-gold)" strokeWidth="1.8" />
        <circle cx="60" cy="60" r="1.6" fill="var(--accent-gold)" />
      </motion.g>
    </svg>
  );
}
