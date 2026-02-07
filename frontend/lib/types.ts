export type Mode = "live" | "demo" | "unknown";

export interface HealthResponse {
  status?: string;
  mode?: string;
  demo_mode?: boolean | number | string;
  data_source?: string;
  updated_at?: string;
  last_updated?: string;
  [key: string]: unknown;
}

export interface MarketSnapshotResponse {
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
  strengths?: string[];
  [key: string]: unknown;
}

export interface MatchData {
  id?: string | number;
  student_id?: string | number;
  name?: string;
  candidate_name?: string;
  score?: number | string;
  rationale?: string;
  skills?: string[];
  location?: string;
  [key: string]: unknown;
}
