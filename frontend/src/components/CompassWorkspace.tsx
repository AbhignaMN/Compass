"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  ArrowUp,
  Compass,
  RotateCcw,
  Sparkles,
  UserCircle2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { CompassRose } from "@/components/CompassRose";
import { JobCard } from "@/components/JobCard";
import { ProfileSidebar } from "@/components/ProfileSidebar";
import { RoadmapJourney } from "@/components/RoadmapJourney";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  deleteMemoryItem,
  fetchProfilePanel,
  sendJobFeedback,
  streamChatMessage,
  updateMemoryItem,
  updateProfilePanel,
} from "@/lib/api";
import { DEMO_MEMORIES, DEMO_MESSAGES, DEMO_PROFILE } from "@/lib/demoData";
import type { ChatMessage, MemoryItem, ProfileSnapshot, ThemeId } from "@/lib/types";

const THEME_STORAGE_KEY = "compass_theme_v1";

const STARTER_PROMPTS = [
  {
    heading: "N • Set your heading",
    text: "I'm a fresher, like Python, hate sales, want 50K+ in Bengaluru",
  },
  {
    heading: "E • Explore options",
    text: "I'm not sure which tech career path fits me yet — help me narrow it down",
  },
  {
    heading: "W • Chart a 4-week journey",
    text: "Build me a 4-week learning roadmap for an AI / LLM Engineer internship",
  },
];

export function CompassWorkspace() {
  const [theme, setTheme] = useState<ThemeId>("colourful");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [statusText, setStatusText] = useState("Charting your course...");
  const [profile, setProfile] = useState<ProfileSnapshot | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [profileLoading, setProfileLoading] = useState(true);
  const [mobileProfileOpen, setMobileProfileOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast((curr) => (curr === msg ? null : curr)), 2600);
  }, []);

  // Initialize theme (URL override -> localStorage -> system preference)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlTheme = params.get("theme") as ThemeId | null;
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY) as ThemeId | null;
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;

    const initial: ThemeId =
      urlTheme && ["colourful", "midnight", "mahogany"].includes(urlTheme)
        ? urlTheme
        : saved && ["colourful", "midnight", "mahogany"].includes(saved)
          ? saved
          : prefersDark
            ? "midnight"
            : "colourful";

    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);

    // Optional rich preview mode for visual QA & screenshots
    const preview = params.get("preview");
    if (preview === "showcase" || preview === "roadmap") {
      setAutoScrollEnabled(preview === "roadmap");
      setMessages(DEMO_MESSAGES);
      setProfile(DEMO_PROFILE);
      setMemories(DEMO_MEMORIES);
      setProfileLoading(false);
      return;
    }

    fetchProfilePanel()
      .then((data) => {
        setProfile(data.profile);
        setMemories(data.memories);
      })
      .catch(() => {
        // Offline or cold backend — leave empty profile cleanly
      })
      .finally(() => setProfileLoading(false));
  }, []);

  const handleThemeChange = (next: ThemeId) => {
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    window.localStorage.setItem(THEME_STORAGE_KEY, next);
  };

  useEffect(() => {
    if (autoScrollEnabled) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, thinking, autoScrollEnabled]);

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input]);

  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || thinking) return;

      setInput("");
      setLastFailedMessage(null);
      setThinking(true);
      setStatusText("Charting your course...");

      const userMsgId = `u-${Date.now()}`;
      const assistantMsgId = `a-${Date.now() + 1}`;

      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: "user", content: text },
        { id: assistantMsgId, role: "assistant", content: "" },
      ]);

      try {
        await streamChatMessage(text, conversationId, {
          onStatus: (label) => setStatusText(label),
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: m.content + token } : m
              )
            );
          },
          onMeta: (meta) => {
            setConversationId(meta.conversation_id);
            if (meta.profile) setProfile(meta.profile);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      suggested_replies: meta.suggested_replies,
                      recommended_jobs: meta.recommended_jobs,
                      skill_gap: meta.skill_gap,
                      roadmap: meta.roadmap,
                    }
                  : m
              )
            );
          },
        });

        // Refresh profile & memories quietly after turn
        fetchProfilePanel()
          .then((data) => {
            setProfile(data.profile);
            setMemories(data.memories);
          })
          .catch(() => {});
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : "Could not reach Compass backend.";
        setLastFailedMessage(text);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: `I couldn't reach the Compass server right now (${errMsg}). Check that the backend API is running and try again.`,
                  error: true,
                }
              : m
          )
        );
      } finally {
        setThinking(false);
      }
    },
    [conversationId, thinking]
  );

  const handleFeedback = async (jobId: string, action: "saved" | "up" | "down") => {
    try {
      const payload =
        action === "saved" ? { event: "saved" as const } : { rating: action };
      await sendJobFeedback(jobId, payload);
      showToast(
        action === "saved"
          ? "Saved to your bearings"
          : action === "up"
            ? "Noted — we'll boost similar roles"
            : "Got it — we'll show fewer roles like this"
      );
    } catch {
      showToast("Feedback saved locally (API offline)");
    }
  };

  const handleProfileUpdate = async (patch: Partial<Omit<ProfileSnapshot, "user_id">>) => {
    try {
      const updated = await updateProfilePanel(patch);
      setProfile(updated);
      showToast("Profile updated");
    } catch {
      setProfile((prev) => (prev ? { ...prev, ...patch } : prev));
      showToast("Updated locally");
    }
  };

  const handleEditMemory = async (id: string, text: string) => {
    try {
      const updated = await updateMemoryItem(id, text);
      setMemories((prev) => prev.map((m) => (m.id === id ? updated : m)));
      showToast("Memory updated");
    } catch {
      setMemories((prev) => prev.map((m) => (m.id === id ? { ...m, text } : m)));
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await deleteMemoryItem(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      showToast("Memory removed");
    } catch {
      setMemories((prev) => prev.filter((m) => m.id !== id));
    }
  };

  const latestAssistantId = [...messages].reverse().find((m) => m.role === "assistant")?.id;

  return (
    <div className="topo-bg relative flex h-dvh w-full flex-col overflow-hidden">
      {/* Subtle decorative topographic SVG watermark */}
      <svg
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 h-full w-full opacity-80"
        preserveAspectRatio="none"
      >
        <defs>
          <pattern id="topo-lines" width="240" height="240" patternUnits="userSpaceOnUse">
            <path
              d="M0 120 Q 60 70, 120 120 T 240 120 M0 40 Q 80 10, 160 55 T 240 40 M0 200 Q 90 165, 170 210 T 240 200"
              fill="none"
              stroke="var(--topo-stroke)"
              strokeWidth="1.2"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#topo-lines)" />
      </svg>

      {/* Landing Header */}
      <header className="relative z-20 flex shrink-0 items-center justify-between gap-2 border-b border-hairline bg-surface/85 px-3 py-2.5 backdrop-blur-md sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
          <CompassRose size={34} thinking={thinking} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="font-serif text-base font-bold tracking-tight text-ink sm:text-xl">
                Compass
              </h1>
              <span className="hidden rounded-full border border-accent-gold/40 bg-accent-gold/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-gold sm:inline-block">
                AI Career Mentor
              </span>
            </div>
            <p className="truncate text-[11px] text-ink-muted sm:text-xs">
              Find your true north in your career.
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setMessages([]);
                setConversationId(null);
                showToast("Set a new heading");
              }}
              className="hidden items-center gap-1.5 rounded-full border border-hairline bg-surface px-3 py-1.5 text-xs font-medium text-ink-muted transition hover:border-accent-gold hover:text-ink sm:inline-flex"
            >
              <Compass className="h-3.5 w-3.5 text-accent-gold" />
              New heading
            </button>
          )}
          <ThemeToggle theme={theme} onChange={handleThemeChange} />
          <button
            type="button"
            onClick={() => setMobileProfileOpen(true)}
            aria-label="Open your profile panel"
            className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface px-2.5 py-1.5 text-xs font-medium text-ink transition hover:border-accent-gold lg:hidden"
          >
            <UserCircle2 className="h-4 w-4 text-accent" />
            <span className="hidden min-[380px]:inline">Profile</span>
          </button>
        </div>
      </header>

      {/* Main Split Layout */}
      <div className="relative z-10 flex min-h-0 w-full flex-1 overflow-hidden">
        {/* Chat Column */}
        <main className="flex min-w-0 w-full flex-1 flex-col">
          <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-5 sm:px-6 sm:py-6">
            <div className="mx-auto w-full min-w-0 max-w-3xl">
              {messages.length === 0 ? (
                /* Empty State */
                <motion.div
                  initial={false}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center py-8 text-center sm:py-14"
                >
                  <CompassRose size={124} />
                  <h2 className="mt-5 font-serif text-2xl font-semibold text-ink sm:text-3xl">
                    Where would you like to head next?
                  </h2>
                  <p className="mt-2 max-w-lg text-sm leading-relaxed text-ink-muted">
                    Tell me what you enjoy, what you want to avoid, or where you feel stuck.
                    I&apos;ll match you with real fresher roles, spot your exact skill gaps, and
                    chart a practical 4-week journey.
                  </p>

                  <div className="mt-8 grid w-full gap-3 sm:grid-cols-3">
                    {STARTER_PROMPTS.map((item) => (
                      <button
                        key={item.heading}
                        type="button"
                        onClick={() => sendMessage(item.text)}
                        className="group rounded-2xl border border-hairline bg-surface/90 p-4 text-left shadow-card transition hover:-translate-y-0.5 hover:border-accent-gold"
                      >
                        <div className="text-[10px] font-semibold uppercase tracking-widest text-accent-gold">
                          {item.heading}
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-ink group-hover:text-accent">
                          &ldquo;{item.text}&rdquo;
                        </p>
                      </button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                /* Message Stream */
                <div className="space-y-6 pb-4">
                  {messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={false}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex w-full min-w-0 flex-col ${
                        msg.role === "user" ? "items-end" : "items-start"
                      }`}
                    >
                      {msg.role === "user" ? (
                        <div className="user-bubble max-w-[90%] break-words rounded-2xl rounded-br-sm px-4 py-3 text-sm leading-relaxed shadow-card sm:max-w-[75%]">
                          {msg.content}
                        </div>
                      ) : (
                        <div className="w-full min-w-0 space-y-4">
                          {(msg.content || msg.error) && (
                            <div
                              className={`max-w-full break-words rounded-2xl rounded-bl-sm border px-4 py-3.5 text-sm leading-relaxed shadow-card sm:max-w-[88%] ${
                                msg.error
                                  ? "border-accent-warm/45 bg-accent-warm/10 text-ink"
                                  : "border-hairline bg-surface text-ink"
                              }`}
                            >
                              {msg.error && (
                                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-accent-warm">
                                  <AlertCircle className="h-4 w-4" /> Connection interrupted
                                </div>
                              )}
                              <div className="prose prose-sm max-w-none text-ink [&_strong]:font-semibold [&_strong]:text-ink [&_ul]:list-disc [&_ul]:pl-5">
                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                              </div>
                              {msg.error && lastFailedMessage && (
                                <button
                                  type="button"
                                  onClick={() => sendMessage(lastFailedMessage)}
                                  className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg border border-accent-warm/40 bg-surface px-3 py-1 text-xs font-medium text-ink hover:border-accent-gold"
                                >
                                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                                </button>
                              )}
                            </div>
                          )}

                          {/* Grounded Job Cards */}
                          {msg.recommended_jobs && msg.recommended_jobs.length > 0 && (
                            <div className="grid gap-3 sm:grid-cols-1">
                              {msg.recommended_jobs.map((job) => (
                                <JobCard
                                  key={job.job_id}
                                  job={job}
                                  onFeedback={handleFeedback}
                                  onQuickPrompt={(p) => sendMessage(p)}
                                />
                              ))}
                            </div>
                          )}

                          {/* Roadmap Journey */}
                          {msg.roadmap && <RoadmapJourney plan={msg.roadmap} />}

                          {/* Suggested Follow-up Chips */}
                          {msg.id === latestAssistantId &&
                            !thinking &&
                            msg.suggested_replies &&
                            msg.suggested_replies.length > 0 && (
                              <div className="flex flex-wrap gap-2 pt-1">
                                {msg.suggested_replies.map((chip) => (
                                  <button
                                    key={chip}
                                    type="button"
                                    onClick={() => sendMessage(chip)}
                                    className="inline-flex items-center gap-1.5 rounded-full border border-accent-gold/45 bg-surface px-3.5 py-1.5 text-xs font-medium text-ink shadow-sm transition hover:-translate-y-0.5 hover:border-accent-gold hover:bg-surface-muted"
                                  >
                                    <Sparkles className="h-3 w-3 text-accent-gold" />
                                    {chip}
                                  </button>
                                ))}
                              </div>
                            )}
                        </div>
                      )}
                    </motion.div>
                  ))}

                  {/* Animated Compass Thinking State */}
                  {thinking && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex items-center gap-3 rounded-2xl border border-hairline bg-surface/90 px-4 py-3 text-xs text-ink-muted shadow-sm"
                    >
                      <CompassRose size={30} thinking decorative />
                      <span className="font-medium text-ink">{statusText}</span>
                    </motion.div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>
          </div>

          {/* Bottom-Anchored Composer */}
          <div className="shrink-0 border-t border-hairline bg-surface/90 px-4 py-3 backdrop-blur-md sm:px-6">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
              className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-hairline bg-canvas/85 p-2 shadow-sm focus-within:border-accent-gold"
            >
              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage(input);
                  }
                }}
                placeholder="Ask Compass about roles, skill gaps, salaries, or a 4-week roadmap..."
                aria-label="Message Compass"
                className="max-h-36 flex-1 resize-none bg-transparent px-2.5 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none"
              />
              <button
                type="submit"
                disabled={thinking || !input.trim()}
                aria-label="Send message"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-white shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ArrowUp className="h-4 w-4" />
              </button>
            </form>
          </div>
        </main>

        {/* Desktop Profile Sidebar */}
        <div className="hidden w-80 shrink-0 lg:block xl:w-88">
          <ProfileSidebar
            profile={profile}
            memories={memories}
            loading={profileLoading}
            onUpdateProfile={handleProfileUpdate}
            onEditMemory={handleEditMemory}
            onDeleteMemory={handleDeleteMemory}
          />
        </div>
      </div>

      {/* Mobile Profile Drawer */}
      <AnimatePresence>
        {mobileProfileOpen && (
          <div className="fixed inset-0 z-50 flex justify-end lg:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileProfileOpen(false)}
              className="fixed inset-0 bg-black/50 backdrop-blur-xs"
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 24, stiffness: 220 }}
              className="relative z-10 h-full w-80 max-w-[90vw]"
            >
              <ProfileSidebar
                profile={profile}
                memories={memories}
                loading={profileLoading}
                onUpdateProfile={handleProfileUpdate}
                onEditMemory={handleEditMemory}
                onDeleteMemory={handleDeleteMemory}
                onCloseMobile={() => setMobileProfileOpen(false)}
              />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            role="status"
            className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-full border border-accent-gold/50 bg-surface px-4 py-2 text-xs font-medium text-ink shadow-card"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
