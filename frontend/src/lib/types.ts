export type ThemeId = "colourful" | "midnight" | "mahogany";

export interface ScoreBreakdown {
  semantic: number;
  skill_overlap: number;
  preference_fit: number;
  freshness: number;
  interaction_adjustment: number;
  final_score: number;
}

export interface RankedJob {
  job_id: string;
  title: string;
  company: string;
  location: string;
  remote: boolean;
  salary_min: number | null;
  salary_max: number | null;
  source: string;
  source_url: string;
  posted_at: string;
  fit_score_pct: number;
  fit_label: "True North" | "Heading right" | "Detour";
  scores: ScoreBreakdown;
  matched_skills: string[];
  missing_skills: string[];
  why_it_fits: string;
}

export interface SkillGapItem {
  skill: string;
  category: string;
  importance: number;
  importance_label: "must-have" | "core" | "nice-to-have";
}

export interface SkillGapResult {
  job_id: string;
  job_title: string;
  company: string;
  matched_skills: string[];
  missing_skills: SkillGapItem[];
  coverage_pct: number;
}

export interface RoadmapWeek {
  week: number;
  goal: string;
  resource: string;
  project: string;
  outcome: string;
}

export interface RoadmapAlternative {
  role: string;
  tradeoff: string;
}

export interface RoadmapSource {
  source_url: string;
  title: string;
}

export interface RoadmapPlan {
  target_role: string;
  fit_score: number;
  ranked_gaps: string[];
  weeks: RoadmapWeek[];
  apply_when: string;
  alternatives: RoadmapAlternative[];
  sources: RoadmapSource[];
}

export interface ProfileSnapshot {
  user_id: string;
  skills: string[];
  interests: string[];
  location_pref: string | null;
  remote_ok: boolean;
  salary_min: number | null;
  experience_level: string | null;
  goals: string | null;
}

export interface MemoryItem {
  id: string;
  type: "fact" | "preference" | "goal";
  text: string;
  last_seen: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  recommended_jobs?: RankedJob[];
  skill_gap?: SkillGapResult | null;
  roadmap?: RoadmapPlan | null;
  suggested_replies?: string[];
  error?: boolean;
}
