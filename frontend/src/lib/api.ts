import type {
  MemoryItem,
  ProfileSnapshot,
  RankedJob,
  RoadmapPlan,
  SkillGapResult,
} from "./types";

const UID_STORAGE_KEY = "compass_anonymous_uid";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl && envUrl.trim()) return envUrl.replace(/\/$/, "");
    // When served statically by FastAPI (same origin), use relative paths
    if (window.location.port === "8000" || window.location.hostname !== "localhost") {
      return "";
    }
  }
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
}

export function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "";
  let uid = window.localStorage.getItem(UID_STORAGE_KEY);
  if (!uid) {
    uid =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : "00000000-0000-4000-8000-000000000001";
    window.localStorage.setItem(UID_STORAGE_KEY, uid);
  }
  return uid;
}

function authHeaders(): Record<string, string> {
  const uid = getOrCreateUserId();
  return uid
    ? { "Content-Type": "application/json", "X-Compass-User-Id": uid }
    : { "Content-Type": "application/json" };
}

export interface StreamCallbacks {
  onStatus: (status: string) => void;
  onToken: (token: string) => void;
  onMeta: (meta: {
    conversation_id: string;
    user_id: string;
    suggested_replies: string[];
    recommended_jobs: RankedJob[];
    skill_gap: SkillGapResult | null;
    roadmap: RoadmapPlan | null;
    profile: ProfileSnapshot | null;
  }) => void;
}

export async function streamChatMessage(
  message: string,
  conversationId: string | null,
  callbacks: StreamCallbacks
): Promise<void> {
  const resp = await fetch(`${getApiBaseUrl()}/chat`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      Accept: "text/event-stream",
    },
    credentials: "include",
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      stream: true,
    }),
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Compass API returned HTTP ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      let eventType = "message";
      let dataLine = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
      }
      if (!dataLine) continue;
      try {
        const parsed = JSON.parse(dataLine);
        if (eventType === "status" && parsed.message) {
          callbacks.onStatus(parsed.message);
        } else if (eventType === "token" && typeof parsed.token === "string") {
          callbacks.onToken(parsed.token);
        } else if (eventType === "meta") {
          if (parsed.user_id && typeof window !== "undefined") {
            window.localStorage.setItem(UID_STORAGE_KEY, parsed.user_id);
          }
          callbacks.onMeta(parsed);
        } else if (eventType === "error") {
          throw new Error(parsed.message || "Stream error");
        }
      } catch (err) {
        if (eventType === "error") throw err;
      }
    }
  }
}

export async function fetchProfilePanel(): Promise<{
  profile: ProfileSnapshot;
  memories: MemoryItem[];
}> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2500);
  try {
    const resp = await fetch(`${getApiBaseUrl()}/profile`, {
      headers: authHeaders(),
      credentials: "include",
      signal: controller.signal,
    });
    if (!resp.ok) throw new Error(`Profile HTTP ${resp.status}`);
    return await resp.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function updateProfilePanel(
  patch: Partial<Omit<ProfileSnapshot, "user_id">>
): Promise<ProfileSnapshot> {
  const resp = await fetch(`${getApiBaseUrl()}/profile`, {
    method: "PATCH",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify(patch),
  });
  if (!resp.ok) throw new Error(`Update profile HTTP ${resp.status}`);
  return resp.json();
}

export async function updateMemoryItem(id: string, text: string): Promise<MemoryItem> {
  const resp = await fetch(`${getApiBaseUrl()}/memories/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify({ text }),
  });
  if (!resp.ok) throw new Error(`Update memory HTTP ${resp.status}`);
  return resp.json();
}

export async function deleteMemoryItem(id: string): Promise<void> {
  const resp = await fetch(`${getApiBaseUrl()}/memories/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
    credentials: "include",
  });
  if (!resp.ok) throw new Error(`Delete memory HTTP ${resp.status}`);
}

export async function sendJobFeedback(
  jobId: string,
  payload: { event?: "shown" | "clicked" | "saved" | "dismissed"; rating?: "up" | "down" }
): Promise<void> {
  const resp = await fetch(`${getApiBaseUrl()}/feedback`, {
    method: "POST",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify({ job_id: jobId, ...payload }),
  });
  if (!resp.ok) throw new Error(`Feedback HTTP ${resp.status}`);
}
