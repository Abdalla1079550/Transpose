"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { MetricTile } from "@/components/MetricTile";
import { ModeIndicator } from "@/components/ModeIndicator";
import { SurfaceCard } from "@/components/SurfaceCard";
import { BACKEND_URL, getDemoCached, getHealth, getMarketSnapshot } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
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

  const nestedPayloads = asRecord(record.payloads);
  if (nestedPayloads) {
    const market = asRecord(nestedPayloads.market_snapshot ?? nestedPayloads["market_snapshot.json"]);
    if (market) {
      return market;
    }
  }

  const nested = asRecord(record.market_snapshot ?? record.snapshot ?? record.market);
  if (nested) {
    return nested;
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
  const epochValue = snapshot.updated_at_epoch_ms;
  if (typeof epochValue === "number") {
    return formatDateTime(new Date(epochValue).toISOString());
  }

  const raw =
    (typeof snapshot.updated_at === "string" && snapshot.updated_at) ||
    (typeof snapshot.generated_at === "string" && snapshot.generated_at) ||
    (typeof health.updated_at === "string" && health.updated_at) ||
    (typeof health.last_updated === "string" && health.last_updated);

  return formatDateTime(raw);
}

function collectMetrics(snapshot: SnapshotRecord): MetricItem[] {
  const totalOpenings = snapshot.total_openings_estimate;
  const trend = asRecord(snapshot.trend);

  const trendPct =
    typeof trend?.pct_change === "number"
      ? `${formatNumber(trend.pct_change)}%`
      : typeof trend?.pct_change === "string"
        ? trend.pct_change
        : "--";

  const currentWindow = trend?.current_window;
  const previousWindow = trend?.previous_window;

  return [
    {
      label: "Hiring Now",
      value: formatNumber(totalOpenings),
      hint: "Estimated active openings"
    },
    {
      label: "Trend",
      value: trendPct,
      hint: "Last window vs previous window"
    },
    {
      label: "Current Window",
      value: formatNumber(currentWindow),
      hint: "Observed market signal volume"
    },
    {
      label: "Previous Window",
      value: formatNumber(previousWindow),
      hint: "Baseline for trend comparison"
    }
  ];
}

function toCompanyItems(raw: unknown): DisplayItem[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .map((entry): DisplayItem | null => {
      const record = asRecord(entry);
      if (!record) {
        return null;
      }
      const title =
        (typeof record.company_name === "string" && record.company_name) ||
        (typeof record.name === "string" && record.name) ||
        "";
      if (!title) {
        return null;
      }

      const detail =
        (typeof record.industry === "string" && record.industry) ||
        (typeof record.location === "string" && record.location) ||
        "Unknown";
      const openings = record.openings_estimate ?? record.openings ?? record.job_openings;

      return {
        title,
        detail,
        trailing: openings !== undefined ? `${formatNumber(openings)} openings` : undefined
      };
    })
    .filter((item): item is DisplayItem => item !== null)
    .slice(0, 10);
}

function toSignalItems(snapshot: SnapshotRecord): DisplayItem[] {
  const industries = Array.isArray(snapshot.top_industries) ? snapshot.top_industries : [];
  const skills = Array.isArray(snapshot.top_skills) ? snapshot.top_skills : [];
  const items: DisplayItem[] = [];

  for (const industry of industries.slice(0, 4)) {
    const record = asRecord(industry);
    if (!record) {
      continue;
    }
    const name = typeof record.industry === "string" ? record.industry : "Unknown";
    items.push({
      title: `Industry: ${name}`,
      detail: "Hiring concentration",
      trailing: formatNumber(record.count)
    });
  }

  for (const skill of skills.slice(0, 6)) {
    const record = asRecord(skill);
    if (!record) {
      continue;
    }
    const name = typeof record.skill === "string" ? record.skill : "Unknown";
    items.push({
      title: `Skill: ${name}`,
      detail: "Frequency in market signals",
      trailing: formatNumber(record.count)
    });
  }

  return items;
}

function downloadText(filename: string, content: string, type: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function MarketTruthPage() {
  const [region, setRegion] = useState("AE");
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
    () => toCompanyItems(snapshot.listings_or_companies_sample ?? snapshot.top_companies ?? snapshot.companies),
    [snapshot]
  );
  const signals = useMemo(() => toSignalItems(snapshot), [snapshot]);

  const mode = inferMode(snapshot, health, usedDemoFallback);
  const source = inferSource(snapshot, health, usedDemoFallback);
  const lastUpdated = inferLastUpdated(snapshot, health);

  const exportBriefJson = () => {
    const payload = {
      region,
      role_cluster: roleCluster,
      generated_at: new Date().toISOString(),
      trend: snapshot.trend ?? {},
      top_skills: snapshot.top_skills ?? [],
      top_industries: snapshot.top_industries ?? []
    };
    downloadText(
      `curriculum_gap_brief_${region}_${roleCluster}.json`,
      JSON.stringify(payload, null, 2),
      "application/json"
    );
  };

  const exportBriefCsv = () => {
    const skills = Array.isArray(snapshot.top_skills) ? snapshot.top_skills : [];
    const rows = ["skill,count"];
    for (const item of skills) {
      const record = asRecord(item);
      if (!record) {
        continue;
      }
      const skill = typeof record.skill === "string" ? record.skill : "";
      const count = record.count !== undefined ? String(record.count) : "0";
      if (skill) {
        rows.push(`${skill.replace(/,/g, " ")},${count}`);
      }
    }
    downloadText(`curriculum_gap_brief_${region}_${roleCluster}.csv`, rows.join("\n"), "text/csv");
  };

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
          <div className="surface-actions">
            <button className="ghost-button" onClick={exportBriefJson} type="button">
              Export JSON
            </button>
            <button className="ghost-button" onClick={exportBriefCsv} type="button">
              Export CSV
            </button>
            <button className="primary-button" onClick={() => setRefreshToken((v) => v + 1)} type="button">
              Refresh
            </button>
          </div>
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
              maxLength={8}
              placeholder="AE"
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

            <SurfaceCard title="Signal Log" subtitle="Top industries and skill demand indicators">
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
                      {item.trailing && <p className="line-trailing">{item.trailing}</p>}
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
