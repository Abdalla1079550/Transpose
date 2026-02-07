"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { MetricTile } from "@/components/MetricTile";
import { ModeIndicator } from "@/components/ModeIndicator";
import { SurfaceCard } from "@/components/SurfaceCard";
import { BACKEND_URL, getDemoCached, getHealth, getMarketSnapshot } from "@/lib/api";
import { formatDateTime, formatNumber, toHeadline } from "@/lib/format";
import type { HealthResponse, MetricItem, Mode } from "@/lib/types";

type SnapshotRecord = Record<string, unknown>;

type DisplayItem = {
  title: string;
  detail: string;
  trailing?: string;
};

function asRecord(value: unknown): SnapshotRecord | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as SnapshotRecord;
  }
  return null;
}

function resolveSnapshotPayload(value: unknown): SnapshotRecord {
  const record = asRecord(value);
  if (!record) {
    return {};
  }
  for (const key of ["market_snapshot", "snapshot", "market"]) {
    const nested = asRecord(record[key]);
    if (nested) {
      return nested;
    }
  }
  return record;
}

function inferMode(snapshot: SnapshotRecord, health: HealthResponse, usedDemoFallback: boolean): Mode {
  if (usedDemoFallback) {
    return "demo";
  }
  const signals: unknown[] = [snapshot.mode, snapshot.demo_mode, health.mode, health.demo_mode];
  for (const signal of signals) {
    if (typeof signal === "string") {
      const normalized = signal.toLowerCase();
      if (normalized.includes("demo")) {
        return "demo";
      }
      if (normalized.includes("live")) {
        return "live";
      }
    }
    if (typeof signal === "boolean") {
      return signal ? "demo" : "live";
    }
    if (typeof signal === "number") {
      return signal === 1 ? "demo" : "live";
    }
  }
  return "unknown";
}

function inferSource(snapshot: SnapshotRecord, health: HealthResponse, usedDemoFallback: boolean): string {
  const source =
    (typeof snapshot.data_source === "string" && snapshot.data_source) ||
    (typeof snapshot.source === "string" && snapshot.source) ||
    (typeof health.data_source === "string" && health.data_source);
  if (source) {
    return source;
  }
  if (usedDemoFallback) {
    return "Cached demo payload";
  }
  return "Backend market snapshot";
}

function inferLastUpdated(snapshot: SnapshotRecord, health: HealthResponse): string {
  const raw =
    (typeof snapshot.last_updated === "string" && snapshot.last_updated) ||
    (typeof snapshot.updated_at === "string" && snapshot.updated_at) ||
    (typeof snapshot.generated_at === "string" && snapshot.generated_at) ||
    (typeof health.last_updated === "string" && health.last_updated) ||
    (typeof health.updated_at === "string" && health.updated_at);

  return formatDateTime(raw);
}

function collectMetrics(snapshot: SnapshotRecord): MetricItem[] {
  const metrics = asRecord(snapshot.metrics);

  const known: Array<{ label: string; value: unknown; hint?: string }> = [
    {
      label: "Open Roles",
      value:
        snapshot.open_roles ?? snapshot.job_openings ?? snapshot.total_openings ?? metrics?.open_roles,
      hint: "Current active demand"
    },
    {
      label: "Hiring Companies",
      value:
        snapshot.hiring_companies ??
        snapshot.total_companies ??
        snapshot.company_count ??
        metrics?.hiring_companies,
      hint: "Distinct employers in window"
    },
    {
      label: "Market Momentum",
      value: snapshot.momentum ?? snapshot.market_momentum ?? metrics?.momentum,
      hint: "Relative week-over-week trend"
    },
    {
      label: "Signal Confidence",
      value: snapshot.confidence ?? metrics?.confidence,
      hint: "Data reliability at refresh"
    }
  ];

  const picked = known
    .filter((item) => item.value !== undefined && item.value !== null && item.value !== "")
    .map((item) => ({
      label: item.label,
      value: formatNumber(item.value),
      hint: item.hint
    }));

  if (picked.length > 0) {
    return picked;
  }

  if (metrics) {
    const dynamic = Object.entries(metrics)
      .slice(0, 4)
      .map(([key, value]) => ({ label: toHeadline(key), value: formatNumber(value) }));
    if (dynamic.length > 0) {
      return dynamic;
    }
  }

  return [
    { label: "Open Roles", value: "--" },
    { label: "Hiring Companies", value: "--" },
    { label: "Market Momentum", value: "--" },
    { label: "Signal Confidence", value: "--" }
  ];
}

function toDisplayItems(raw: unknown, type: "company" | "signal"): DisplayItem[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .map((entry): DisplayItem | null => {
      if (typeof entry === "string") {
        return { title: entry, detail: "" };
      }
      const record = asRecord(entry);
      if (!record) {
        return null;
      }

      if (type === "company") {
        const title =
          (typeof record.name === "string" && record.name) ||
          (typeof record.company_name === "string" && record.company_name) ||
          (typeof record.title === "string" && record.title);

        if (!title) {
          return null;
        }

        const detail =
          (typeof record.industry === "string" && record.industry) ||
          (typeof record.location === "string" && record.location) ||
          "Industry unavailable";

        const openingsRaw = record.openings ?? record.job_openings ?? record.roles;

        return {
          title,
          detail,
          trailing: openingsRaw !== undefined ? `${formatNumber(openingsRaw)} openings` : undefined
        };
      }

      const title =
        (typeof record.title === "string" && record.title) ||
        (typeof record.signal === "string" && record.signal) ||
        (typeof record.name === "string" && record.name);

      if (!title) {
        return null;
      }

      const detail =
        (typeof record.detail === "string" && record.detail) ||
        (typeof record.summary === "string" && record.summary) ||
        (typeof record.description === "string" && record.description) ||
        "";

      return { title, detail };
    })
    .filter((item): item is DisplayItem => item !== null)
    .slice(0, 6);
}

export default function MarketTruthPage() {
  const [region, setRegion] = useState("US");
  const [roleCluster, setRoleCluster] = useState("data_analyst");
  const [days, setDays] = useState(7);
  const [refreshToken, setRefreshToken] = useState(0);

  const [snapshot, setSnapshot] = useState<SnapshotRecord>({});
  const [health, setHealth] = useState<HealthResponse>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usedDemoFallback, setUsedDemoFallback] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [healthResult, snapshotResult] = await Promise.all([
      getHealth(),
      getMarketSnapshot({ region, role_cluster: roleCluster, days })
    ]);

    if (healthResult.ok) {
      setHealth(healthResult.data);
    }

    if (snapshotResult.ok) {
      setSnapshot(resolveSnapshotPayload(snapshotResult.data));
      setUsedDemoFallback(false);
      setLoading(false);
      return;
    }

    const demoResult = await getDemoCached();
    if (demoResult.ok) {
      setSnapshot(resolveSnapshotPayload(demoResult.data));
      setUsedDemoFallback(true);
      setError(`Snapshot endpoint unavailable (${snapshotResult.error}). Showing demo cache.`);
    } else {
      setSnapshot({});
      setUsedDemoFallback(false);
      setError(snapshotResult.error);
    }

    setLoading(false);
  }, [days, region, roleCluster]);

  useEffect(() => {
    void loadData();
  }, [loadData, refreshToken]);

  const metrics = useMemo(() => collectMetrics(snapshot), [snapshot]);
  const companies = useMemo(
    () => toDisplayItems(snapshot.top_companies ?? snapshot.companies, "company"),
    [snapshot]
  );
  const signals = useMemo(
    () => toDisplayItems(snapshot.signals ?? snapshot.trends ?? snapshot.insights, "signal"),
    [snapshot]
  );

  const mode = inferMode(snapshot, health, usedDemoFallback);
  const source = inferSource(snapshot, health, usedDemoFallback);
  const lastUpdated = inferLastUpdated(snapshot, health);

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <p className="eyebrow">Market Truth Dashboard</p>
          <h1 className="page-title">Demand calibration for edge talent markets</h1>
        </div>
        <ModeIndicator mode={mode} />
      </section>

      <SurfaceCard
        title="Snapshot Controls"
        subtitle="Tune region, role cluster, and time window"
        actions={
          <button className="primary-button" onClick={() => setRefreshToken((v) => v + 1)} type="button">
            Refresh
          </button>
        }
      >
        <div className="meta-row">
          <p>
            Data source: <span className="meta-strong">{source}</span>
          </p>
          <p>
            Last updated: <span className="meta-strong">{lastUpdated}</span>
          </p>
          <p>
            Backend: <span className="meta-strong">{BACKEND_URL}</span>
          </p>
        </div>

        <form
          className="control-grid"
          onSubmit={(event) => {
            event.preventDefault();
            setRefreshToken((v) => v + 1);
          }}
        >
          <label className="field">
            Region
            <input
              value={region}
              onChange={(event) => setRegion(event.target.value.toUpperCase())}
              maxLength={3}
              placeholder="US"
            />
          </label>

          <label className="field">
            Role cluster
            <input
              value={roleCluster}
              onChange={(event) => setRoleCluster(event.target.value)}
              placeholder="data_analyst"
            />
          </label>

          <label className="field">
            Window (days)
            <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
              <option value={7}>7</option>
              <option value={14}>14</option>
              <option value={30}>30</option>
            </select>
          </label>

          <button className="secondary-button" type="submit">
            Apply
          </button>
        </form>

        {error && <ErrorState compact title="Data warning" message={error} onRetry={loadData} />}
      </SurfaceCard>

      {loading && <p className="muted-copy">Refreshing market signals…</p>}

      {!loading && Object.keys(snapshot).length === 0 && !error && (
        <ErrorState
          message="No snapshot data returned from backend for this filter set."
          onRetry={() => setRefreshToken((v) => v + 1)}
        />
      )}

      {Object.keys(snapshot).length > 0 && (
        <>
          <div className="metrics-grid">
            {metrics.map((metric) => (
              <MetricTile key={metric.label} label={metric.label} value={metric.value} hint={metric.hint} />
            ))}
          </div>

          <div className="two-column-grid">
            <SurfaceCard title="Hiring Leaders" subtitle="Most active employers in current window">
              {companies.length === 0 ? (
                <p className="muted-copy">No company ranking returned in this payload.</p>
              ) : (
                <ul className="line-list">
                  {companies.map((item) => (
                    <li key={`${item.title}-${item.trailing || ""}`} className="line-list-item">
                      <div>
                        <p className="line-title">{item.title}</p>
                        {item.detail && <p className="line-detail">{item.detail}</p>}
                      </div>
                      {item.trailing && <p className="line-trailing">{item.trailing}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </SurfaceCard>

            <SurfaceCard title="Signal Log" subtitle="Structured qualitative demand observations">
              {signals.length === 0 ? (
                <p className="muted-copy">No trend signals returned in this payload.</p>
              ) : (
                <ul className="line-list">
                  {signals.map((item) => (
                    <li key={`${item.title}-${item.detail}`} className="line-list-item">
                      <div>
                        <p className="line-title">{item.title}</p>
                        {item.detail && <p className="line-detail">{item.detail}</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </SurfaceCard>
          </div>
        </>
      )}
    </div>
  );
}
