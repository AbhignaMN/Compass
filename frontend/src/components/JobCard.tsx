"use client";

import { motion } from "framer-motion";
import { Bookmark, MapPin, Sparkles, ThumbsDown, ThumbsUp, Wallet } from "lucide-react";
import { useState } from "react";

import { FitCompassDial } from "@/components/FitCompassDial";
import type { RankedJob } from "@/lib/types";

interface JobCardProps {
  job: RankedJob;
  onFeedback: (jobId: string, action: "saved" | "up" | "down") => void;
  onQuickPrompt: (prompt: string) => void;
}

function formatMonthlyInr(min: number | null, max: number | null): string {
  if (!min && !max) return "Salary undisclosed";
  const fmt = (v: number) => `₹${Math.round(v / 1000)}K`;
  if (min && max && min !== max) return `${fmt(min)}–${fmt(max)}/mo`;
  return `${fmt(min || max || 0)}/mo`;
}

export function JobCard({ job, onFeedback, onQuickPrompt }: JobCardProps) {
  const [saved, setSaved] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);

  return (
    <motion.article
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="relative w-full min-w-0 overflow-hidden rounded-2xl border border-hairline bg-surface shadow-card transition hover:border-accent-gold/60"
    >
      <div className="card-accent-strip h-1 w-full opacity-90" />
      <div className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h4 className="font-serif text-base font-semibold leading-snug text-ink">
              {job.title}
            </h4>
            <p className="mt-0.5 text-xs font-medium text-ink-muted">{job.company}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
              <span className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2.5 py-0.5">
                <MapPin className="h-3 w-3 text-accent" />
                {job.location}
              </span>
              {job.remote && (
                <span className="inline-flex items-center rounded-full bg-accent-leaf/15 px-2 py-0.5 font-medium text-accent-leaf">
                  Remote
                </span>
              )}
              <span className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2.5 py-0.5 font-medium text-ink">
                <Wallet className="h-3 w-3 text-accent-gold" />
                {formatMonthlyInr(job.salary_min, job.salary_max)}
              </span>
            </div>
          </div>

          <FitCompassDial scorePct={job.fit_score_pct} label={job.fit_label} />
        </div>

        {/* Why it fits */}
        <p className="mt-3 rounded-xl bg-surface-muted/75 px-3 py-2 text-xs leading-relaxed text-ink">
          <Sparkles className="mr-1.5 inline h-3.5 w-3.5 text-accent-gold" />
          {job.why_it_fits}
        </p>

        {/* Skills breakdown */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.matched_skills.slice(0, 5).map((skill) => (
            <span
              key={`m-${skill}`}
              className="rounded-full border border-accent-leaf/30 bg-accent-leaf/10 px-2.5 py-0.5 text-[11px] font-medium text-accent-leaf"
            >
              ✓ {skill}
            </span>
          ))}
          {job.missing_skills.slice(0, 4).map((skill) => (
            <span
              key={`g-${skill}`}
              className="rounded-full border border-accent-warm/30 bg-accent-warm/10 px-2.5 py-0.5 text-[11px] font-medium text-accent-warm"
            >
              + learn {skill}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-hairline pt-3">
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() =>
                onQuickPrompt(`Check my detailed skill gap for ${job.title} at ${job.company} (job_id: ${job.job_id})`)
              }
              className="rounded-lg border border-hairline px-2.5 py-1 text-[11px] font-medium text-ink transition hover:border-accent-gold hover:bg-surface-muted"
            >
              Skill gaps
            </button>
            <button
              type="button"
              onClick={() =>
                onQuickPrompt(`Tailor my resume summary for ${job.title} at ${job.company} (job_id: ${job.job_id})`)
              }
              className="rounded-lg border border-hairline px-2.5 py-1 text-[11px] font-medium text-ink transition hover:border-accent-gold hover:bg-surface-muted"
            >
              Tailor resume
            </button>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Thumbs up this job"
              onClick={() => {
                setVote("up");
                onFeedback(job.job_id, "up");
              }}
              className={`rounded-lg p-1.5 transition ${
                vote === "up"
                  ? "bg-accent-leaf/20 text-accent-leaf"
                  : "text-ink-muted hover:bg-surface-muted hover:text-ink"
              }`}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              aria-label="Thumbs down this job"
              onClick={() => {
                setVote("down");
                onFeedback(job.job_id, "down");
              }}
              className={`rounded-lg p-1.5 transition ${
                vote === "down"
                  ? "bg-accent-warm/20 text-accent-warm"
                  : "text-ink-muted hover:bg-surface-muted hover:text-ink"
              }`}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              aria-label="Save this job"
              onClick={() => {
                setSaved((s) => !s);
                onFeedback(job.job_id, "saved");
              }}
              className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-[11px] font-medium transition ${
                saved
                  ? "border-accent-gold bg-accent-gold/15 text-accent-gold"
                  : "border-hairline text-ink-muted hover:border-accent-gold hover:text-ink"
              }`}
            >
              <Bookmark className="h-3 w-3" />
              {saved ? "Saved" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </motion.article>
  );
}
