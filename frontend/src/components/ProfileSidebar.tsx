"use client";

import { Check, Compass, Edit3, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import type { MemoryItem, ProfileSnapshot } from "@/lib/types";

interface ProfileSidebarProps {
  profile: ProfileSnapshot | null;
  memories: MemoryItem[];
  loading: boolean;
  onUpdateProfile: (patch: Partial<Omit<ProfileSnapshot, "user_id">>) => Promise<void>;
  onEditMemory: (id: string, text: string) => Promise<void>;
  onDeleteMemory: (id: string) => Promise<void>;
  onCloseMobile?: () => void;
}

export function ProfileSidebar({
  profile,
  memories,
  loading,
  onUpdateProfile,
  onEditMemory,
  onDeleteMemory,
  onCloseMobile,
}: ProfileSidebarProps) {
  const [newSkill, setNewSkill] = useState("");
  const [editingCity, setEditingCity] = useState(false);
  const [cityDraft, setCityDraft] = useState("");
  const [salaryDraft, setSalaryDraft] = useState("");
  const [editingMemId, setEditingMemId] = useState<string | null>(null);
  const [memDraft, setMemDraft] = useState("");

  const handleAddSkill = async () => {
    const trimmed = newSkill.trim();
    if (!trimmed || !profile) return;
    const merged = Array.from(new Set([...profile.skills, trimmed.toLowerCase()]));
    setNewSkill("");
    await onUpdateProfile({ skills: merged });
  };

  const handleRemoveSkill = async (skill: string) => {
    if (!profile) return;
    await onUpdateProfile({ skills: profile.skills.filter((s) => s !== skill) });
  };

  const startEditBearings = () => {
    setCityDraft(profile?.location_pref || "");
    setSalaryDraft(profile?.salary_min ? String(profile.salary_min) : "");
    setEditingCity(true);
  };

  const saveBearings = async () => {
    await onUpdateProfile({
      location_pref: cityDraft.trim() || null,
      salary_min: salaryDraft.trim() ? Number(salaryDraft) : null,
    });
    setEditingCity(false);
  };

  const typeBadge = (type: MemoryItem["type"]) => {
    if (type === "goal") return "bg-accent-gold/15 text-accent-gold";
    if (type === "preference") return "bg-accent/15 text-accent";
    return "bg-accent-leaf/15 text-accent-leaf";
  };

  return (
    <aside className="flex h-full flex-col border-l border-hairline bg-surface/95 backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3.5">
        <div className="flex items-center gap-2">
          <Compass className="h-4 w-4 text-accent-gold" />
          <div>
            <h2 className="font-serif text-sm font-semibold text-ink">Your Bearings</h2>
            <p className="text-[11px] text-ink-muted">Learned profile & memory</p>
          </div>
        </div>
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            aria-label="Close profile panel"
            className="rounded-lg p-1.5 text-ink-muted hover:bg-surface-muted hover:text-ink lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {loading && !profile ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-16 rounded-xl bg-surface-muted" />
            <div className="h-24 rounded-xl bg-surface-muted" />
            <div className="h-20 rounded-xl bg-surface-muted" />
          </div>
        ) : (
          <>
            {/* Preferences card */}
            <section className="rounded-2xl border border-hairline bg-surface-muted/50 p-3.5">
              <div className="flex items-center justify-between">
                <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                  Profile Preferences
                </h3>
                {!editingCity && (
                  <button
                    type="button"
                    onClick={startEditBearings}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-accent hover:underline"
                  >
                    <Edit3 className="h-3 w-3" /> Edit
                  </button>
                )}
              </div>

              {editingCity ? (
                <div className="mt-2.5 space-y-2">
                  <input
                    value={cityDraft}
                    onChange={(e) => setCityDraft(e.target.value)}
                    placeholder="City (e.g. Bengaluru)"
                    className="w-full rounded-lg border border-hairline bg-surface px-2.5 py-1.5 text-xs text-ink focus:border-accent-gold focus:outline-none"
                  />
                  <input
                    type="number"
                    value={salaryDraft}
                    onChange={(e) => setSalaryDraft(e.target.value)}
                    placeholder="Min salary INR/mo (e.g. 50000)"
                    className="w-full rounded-lg border border-hairline bg-surface px-2.5 py-1.5 text-xs text-ink focus:border-accent-gold focus:outline-none"
                  />
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={saveBearings}
                      className="inline-flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white"
                    >
                      <Check className="h-3 w-3" /> Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingCity(false)}
                      className="rounded-lg border border-hairline px-2.5 py-1 text-xs text-ink-muted"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <dl className="mt-2.5 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <dt className="text-[10px] uppercase text-ink-muted">Location</dt>
                    <dd className="font-medium text-ink">
                      {profile?.location_pref || "Not set yet"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase text-ink-muted">Min Salary</dt>
                    <dd className="font-medium text-ink">
                      {profile?.salary_min
                        ? `₹${Math.round(profile.salary_min / 1000)}K/mo`
                        : "Flexible"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase text-ink-muted">Level</dt>
                    <dd className="capitalize font-medium text-ink">
                      {profile?.experience_level || "Fresher"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase text-ink-muted">Remote</dt>
                    <dd className="font-medium text-ink">
                      {profile?.remote_ok === false ? "On-site only" : "Open to remote"}
                    </dd>
                  </div>
                </dl>
              )}
            </section>

            {/* Skills */}
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                Skills ({profile?.skills.length || 0})
              </h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(profile?.skills || []).length === 0 ? (
                  <p className="text-xs text-ink-muted">
                    Tell Compass your skills in chat or add them below.
                  </p>
                ) : (
                  profile?.skills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-ink"
                    >
                      {skill}
                      <button
                        type="button"
                        aria-label={`Remove ${skill}`}
                        onClick={() => handleRemoveSkill(skill)}
                        className="text-ink-muted hover:text-accent-warm"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))
                )}
              </div>
              <div className="mt-2.5 flex gap-1.5">
                <input
                  value={newSkill}
                  onChange={(e) => setNewSkill(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddSkill();
                    }
                  }}
                  placeholder="Add skill (e.g. FastAPI)"
                  className="flex-1 rounded-xl border border-hairline bg-surface px-2.5 py-1.5 text-xs text-ink focus:border-accent-gold focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleAddSkill}
                  aria-label="Add skill"
                  className="inline-flex items-center justify-center rounded-xl border border-hairline bg-surface-muted px-2.5 text-ink hover:border-accent-gold"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
            </section>

            {/* Long-term memories */}
            <section>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                Remembered Across Sessions ({memories.length})
              </h3>
              <div className="mt-2 space-y-2">
                {memories.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-hairline p-3 text-xs text-ink-muted">
                    As we chat, Compass automatically remembers your goals, city, and likes/dislikes here.
                  </p>
                ) : (
                  memories.map((mem) => (
                    <div
                      key={mem.id}
                      className="rounded-xl border border-hairline bg-surface-muted/45 p-2.5 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${typeBadge(
                            mem.type
                          )}`}
                        >
                          {mem.type}
                        </span>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            aria-label="Edit memory"
                            onClick={() => {
                              setEditingMemId(mem.id);
                              setMemDraft(mem.text);
                            }}
                            className="rounded p-1 text-ink-muted hover:text-ink"
                          >
                            <Edit3 className="h-3 w-3" />
                          </button>
                          <button
                            type="button"
                            aria-label="Delete memory"
                            onClick={() => onDeleteMemory(mem.id)}
                            className="rounded p-1 text-ink-muted hover:text-accent-warm"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </div>

                      {editingMemId === mem.id ? (
                        <div className="mt-2 space-y-1.5">
                          <textarea
                            rows={2}
                            value={memDraft}
                            onChange={(e) => setMemDraft(e.target.value)}
                            className="w-full rounded-lg border border-hairline bg-surface p-1.5 text-xs text-ink focus:border-accent-gold focus:outline-none"
                          />
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={async () => {
                                await onEditMemory(mem.id, memDraft);
                                setEditingMemId(null);
                              }}
                              className="rounded-md bg-accent px-2 py-0.5 text-[11px] font-medium text-white"
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingMemId(null)}
                              className="rounded-md border border-hairline px-2 py-0.5 text-[11px] text-ink-muted"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="mt-1.5 leading-relaxed text-ink">{mem.text}</p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
