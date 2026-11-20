"use client";

import { motion } from "framer-motion";
import { BookOpen, CheckCircle2, Circle, Compass, Flag, GitFork, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import type { RoadmapPlan } from "@/lib/types";

interface RoadmapJourneyProps {
  plan: RoadmapPlan;
}

const WAYPOINT_DIRECTIONS = ["W", "S", "E", "N"];

export function RoadmapJourney({ plan }: RoadmapJourneyProps) {
  const storageKey = `compass_roadmap_progress_${plan.target_role.toLowerCase().replace(/\s+/g, "_")}`;
  const [completed, setCompleted] = useState<number[]>([]);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) setCompleted(JSON.parse(saved));
    } catch {
      // ignore storage errors
    }
  }, [storageKey]);

  const toggleWeek = (weekNum: number) => {
    setCompleted((prev) => {
      const next = prev.includes(weekNum)
        ? prev.filter((w) => w !== weekNum)
        : [...prev, weekNum];
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const progressPct = Math.round((completed.length / Math.max(1, plan.weeks.length)) * 100);

  return (
    <motion.section
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      className="relative w-full min-w-0 overflow-hidden rounded-2xl border border-hairline bg-surface p-4 shadow-card sm:p-5"
    >
      <div className="card-accent-strip absolute inset-x-0 top-0 h-1" />

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-accent-gold">
            <Compass className="h-3.5 w-3.5" />
            Career Journey Map
          </span>
          <h3 className="mt-1 font-serif text-xl font-semibold text-ink">
            {plan.target_role}
          </h3>
          {plan.ranked_gaps.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-medium text-ink-muted">Priority gaps:</span>
              {plan.ranked_gaps.map((gap) => (
                <span
                  key={gap}
                  className="rounded-full border border-accent-warm/30 bg-accent-warm/10 px-2 py-0.5 text-[11px] font-medium text-accent-warm"
                >
                  {gap}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-hairline bg-surface-muted px-3 py-2 text-right">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
            Journey Progress
          </div>
          <div className="font-serif text-lg font-semibold text-ink">
            {progressPct}%
          </div>
        </div>
      </div>

      {/* Waypoints Timeline */}
      <div className="relative mt-6 space-y-4 pl-9">
        <div
          className="absolute bottom-4 left-3.5 top-2 w-px"
          style={{ background: "var(--border-brass)" }}
        />

        {plan.weeks.map((wk, idx) => {
          const isDone = completed.includes(wk.week);
          const isFinal = idx === plan.weeks.length - 1;
          const dirLabel = isFinal
            ? "N"
            : WAYPOINT_DIRECTIONS[idx % (WAYPOINT_DIRECTIONS.length - 1)];

          return (
            <div key={wk.week} className="relative">
              {/* Waypoint marker */}
              <div
                className={`absolute -left-9 top-3 flex h-7 w-7 items-center justify-center rounded-full border text-[11px] font-bold transition ${
                  isDone
                    ? "border-accent-leaf bg-accent-leaf text-white"
                    : isFinal
                      ? "border-accent-gold bg-surface text-accent-gold shadow-glow"
                      : "border-hairline bg-surface-muted text-ink-muted"
                }`}
              >
                {dirLabel}
              </div>

              <div
                className={`rounded-xl border p-3.5 transition ${
                  isDone
                    ? "border-accent-leaf/40 bg-accent-leaf/5"
                    : "border-hairline bg-surface-muted/55"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-accent-gold">
                      Week {wk.week} {isFinal ? "• True North Milestone" : ""}
                    </span>
                    <h4 className="mt-0.5 text-sm font-semibold text-ink">{wk.goal}</h4>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleWeek(wk.week)}
                    aria-label={`Mark Week ${wk.week} ${isDone ? "incomplete" : "complete"}`}
                    className="shrink-0 rounded-full p-1 text-ink-muted transition hover:text-accent-leaf"
                  >
                    {isDone ? (
                      <CheckCircle2 className="h-5 w-5 text-accent-leaf" />
                    ) : (
                      <Circle className="h-5 w-5" />
                    )}
                  </button>
                </div>

                <dl className="mt-2.5 grid gap-2 text-xs sm:grid-cols-3">
                  <div className="rounded-lg bg-surface/80 p-2">
                    <dt className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                      <BookOpen className="h-3 w-3 text-accent" /> Resource
                    </dt>
                    <dd className="mt-1 text-ink">{wk.resource}</dd>
                  </div>
                  <div className="rounded-lg bg-surface/80 p-2">
                    <dt className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                      <Wrench className="h-3 w-3 text-accent-gold" /> Project
                    </dt>
                    <dd className="mt-1 text-ink">{wk.project}</dd>
                  </div>
                  <div className="rounded-lg bg-surface/80 p-2">
                    <dt className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                      <Flag className="h-3 w-3 text-accent-leaf" /> Outcome
                    </dt>
                    <dd className="mt-1 text-ink">{wk.outcome}</dd>
                  </div>
                </dl>
              </div>
            </div>
          );
        })}
      </div>

      {/* When to apply */}
      <div className="mt-5 rounded-xl border border-accent-gold/35 bg-accent-gold/10 px-3.5 py-2.5 text-xs text-ink">
        <span className="font-semibold text-accent-gold">When to apply: </span>
        {plan.apply_when}
      </div>

      {/* Adjacent roles */}
      {plan.alternatives.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
            <GitFork className="h-3.5 w-3.5 text-accent" /> Adjacent Headings & Trade-offs
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {plan.alternatives.map((alt) => (
              <div
                key={alt.role}
                className="rounded-xl border border-hairline bg-surface-muted/50 p-3 text-xs"
              >
                <div className="font-semibold text-ink">{alt.role}</div>
                <p className="mt-1 text-ink-muted">{alt.tradeoff}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Grounded RAG Citations */}
      {plan.sources.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-hairline pt-3 text-[11px] text-ink-muted">
          <span className="font-semibold">Grounded in:</span>
          {plan.sources.map((src) => (
            <span
              key={src.source_url}
              className="rounded-full border border-hairline bg-surface-muted px-2.5 py-0.5 font-mono text-[10px] text-ink"
            >
              {src.title} ({src.source_url})
            </span>
          ))}
        </div>
      )}
    </motion.section>
  );
}
