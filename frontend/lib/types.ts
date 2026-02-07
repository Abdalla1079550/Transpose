export type Mode = "live" | "demo" | "unknown";

export interface HealthResponse {
  ok?: boolean;
  service?: string;
  mode?: string;
  demo_mode?: boolean | number | string;
  data_source?: string;
  updated_at?: string;
  last_updated?: string;
  [key: string]: unknown;
}

export interface MarketSnapshotResponse {
  role_cluster?: string;
  region?: string;
  window_days?: number;
  total_openings_estimate?: number;
  trend?: {
    current_window?: number;
    previous_window?: number;
    pct_change?: number;
  };
  top_industries?: Array<{ industry?: string; count?: number }>;
  top_skills?: Array<{ skill?: string; count?: number }>;
  listings_or_companies_sample?: unknown[];
  mode?: string;
  demo_mode?: boolean | number | string;
  data_source?: string;
  source?: string;
  generated_at?: string;
  updated_at?: string;
  last_updated?: string;
  metrics?: Record<string, unknown>;
  top_companies?: unknown[];
  signals?: unknown[];
  [key: string]: unknown;
}

export interface MetricItem {
  label: string;
  value: string;
  hint?: string;
}

export interface CandidateCardData {
  candidate?: {
    name?: string;
    email?: string;
    region_pref?: string;
    grad_year?: string | number;
  };
  name?: string;
  full_name?: string;
  candidate_name?: string;
  role?: string;
  target_role?: string;
  location?: string;
  grad_year?: string | number;
  score?: number | string;
  summary?: string;
  rationale?: string;
  skills?: string[];
  normalized_skill_list?: string[];
  role_fit_suggestions?: string[];
  strengths?: string[];
  gaps?: string[];
  improvements?: string[];
  market_context?: {
    region?: string;
    hiring_now_estimate?: number;
    top_market_skills?: string[];
    citation?: string;
  };
  [key: string]: unknown;
}

export interface MatchData {
  id?: string | number;
  student_id?: string | number;
  student_name?: string;
  name?: string;
  candidate_name?: string;
  score?: number | string;
  rationale?: string;
  skills?: string[];
  evidence?: string[];
  gap_flags?: string[];
  hard_filter_passed?: boolean;
  location?: string;
  [key: string]: unknown;
}

export interface OutreachDraft {
  role_id?: number;
  student_id?: number;
  subject?: string;
  body?: string;
}

export interface DemoBootstrapData {
  ok?: boolean;
  dataset_version?: string;
  seeded_at?: string;
  students?: Array<{ id?: number; name?: string }>;
  roles?: Array<{ id?: number; title?: string; region?: string }>;
  showcase?: {
    student_id?: number;
    role_id?: number;
    region?: string;
    role_cluster?: string;
  };
  outreach_previews?: OutreachDraft[];
}
