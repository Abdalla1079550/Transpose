import type { HealthResponse, MarketSnapshotResponse } from "./types";

const FALLBACK_BACKEND_URL = "http://localhost:8000";

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/+$/, "") || FALLBACK_BACKEND_URL;

type QueryValue = string | number | boolean | undefined | null;

export type ApiSuccess<T> = {
  ok: true;
  data: T;
  status: number;
};

export type ApiFailure = {
  ok: false;
  error: string;
  status: number;
};

export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

function withQuery(path: string, query?: Record<string, QueryValue>): string {
  if (!query) {
    return path;
  }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  const suffix = params.toString();
  if (!suffix) {
    return path;
  }
  return `${path}?${suffix}`;
}

function getErrorMessage(payload: unknown, status: number, statusText: string): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }
  if (payload && typeof payload === "object") {
    const maybeDetail = (payload as Record<string, unknown>).detail;
    if (typeof maybeDetail === "string") {
      return maybeDetail;
    }
    if (Array.isArray(maybeDetail)) {
      const joined = maybeDetail
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as Record<string, unknown>).msg);
          }
          return "";
        })
        .filter(Boolean)
        .join("; ");
      if (joined) {
        return joined;
      }
    }
    const maybeMessage = (payload as Record<string, unknown>).message;
    if (typeof maybeMessage === "string" && maybeMessage.trim()) {
      return maybeMessage;
    }
  }

  if (status === 0) {
    return "Unable to reach backend API. Verify NEXT_PUBLIC_BACKEND_URL and backend availability.";
  }
  return `${status} ${statusText || "Request failed"}`;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  query?: Record<string, QueryValue>
): Promise<ApiResult<T>> {
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  const hasBody = options.body !== undefined && options.body !== null;
  if (hasBody && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(`${BACKEND_URL}${withQuery(path, query)}`, {
      ...options,
      headers,
      cache: "no-store"
    });

    const raw = await response.text();
    let payload: unknown = null;
    if (raw) {
      try {
        payload = JSON.parse(raw);
      } catch {
        payload = raw;
      }
    }

    if (!response.ok) {
      return {
        ok: false,
        error: getErrorMessage(payload, response.status, response.statusText),
        status: response.status
      };
    }

    return {
      ok: true,
      data: (payload ?? {}) as T,
      status: response.status
    };
  } catch {
    return {
      ok: false,
      error: getErrorMessage(null, 0, "Network error"),
      status: 0
    };
  }
}

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function getMarketSnapshot(params: { region: string; role_cluster: string; days: number }) {
  return request<MarketSnapshotResponse>("/market/snapshot", {}, params);
}

export function getDemoCached() {
  return request<Record<string, unknown>>("/demo/cached");
}

export function getInterviewQuestions(roleCluster?: string) {
  return request<Record<string, unknown>>("/students/interview-questions", {}, {
    role_cluster: roleCluster
  });
}

export function createStudent(formData: FormData) {
  return request<Record<string, unknown>>("/students", {
    method: "POST",
    body: formData
  });
}

export function submitInterview(studentId: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/students/${studentId}/interview`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getStudentCard(studentId: string) {
  return request<Record<string, unknown>>(`/students/${studentId}/card`);
}

export function createRole(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/roles", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getRoleMatches(roleId: string) {
  return request<Record<string, unknown>>(`/roles/${roleId}/matches`);
}
