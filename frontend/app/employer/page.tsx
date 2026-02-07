"use client";

import { useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { MatchList } from "@/components/MatchList";
import { SurfaceCard } from "@/components/SurfaceCard";
import { BACKEND_URL, createRole, getRoleMatches } from "@/lib/api";
import type { MatchData } from "@/lib/types";

type GenericRecord = Record<string, unknown>;

function asRecord(value: unknown): GenericRecord | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as GenericRecord;
  }
  return null;
}

function extractRoleId(payload: GenericRecord): string | null {
  const direct = payload.id ?? payload.role_id ?? payload.uuid;
  if (typeof direct === "string" || typeof direct === "number") {
    return String(direct);
  }

  const roleObj = asRecord(payload.role);
  const nested = roleObj?.id ?? roleObj?.role_id;
  if (typeof nested === "string" || typeof nested === "number") {
    return String(nested);
  }

  return null;
}

function extractMatches(payload: GenericRecord): MatchData[] {
  const candidates = payload.matches ?? payload.shortlist ?? payload.candidates;
  if (!Array.isArray(candidates)) {
    return [];
  }

  return candidates
    .map((item) => {
      const record = asRecord(item);
      return record ? (record as MatchData) : null;
    })
    .filter((item): item is MatchData => item !== null);
}

export default function EmployerPage() {
  const [title, setTitle] = useState("Data Analyst");
  const [location, setLocation] = useState("Remote (US)");
  const [headcount, setHeadcount] = useState("3");
  const [skills, setSkills] = useState("SQL, Python, Experimentation");
  const [description, setDescription] = useState("");

  const [roleId, setRoleId] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchData[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [roleError, setRoleError] = useState<string | null>(null);
  const [matchesError, setMatchesError] = useState<string | null>(null);

  const fetchMatches = async (id: string) => {
    setMatchesError(null);
    setLoadingMatches(true);
    const result = await getRoleMatches(id);
    setLoadingMatches(false);

    if (!result.ok) {
      setMatches([]);
      setMatchesError(result.error);
      return;
    }

    setMatches(extractMatches(result.data));
  };

  const createRoleAndFetch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRoleError(null);

    const mustHaveSkills = skills
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    const payload = {
      role_title: title,
      title,
      location,
      headcount: Number(headcount),
      must_have_skills: mustHaveSkills,
      description
    };

    setSubmitting(true);
    const result = await createRole(payload);
    setSubmitting(false);

    if (!result.ok) {
      setRoleError(result.error);
      return;
    }

    const id = extractRoleId(result.data);
    if (!id) {
      setRoleError("Role created but backend did not return a role id.");
      return;
    }

    setRoleId(id);
    await fetchMatches(id);
  };

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <p className="eyebrow">Employer Workflow</p>
          <h1 className="page-title">Define role constraints and generate shortlist</h1>
        </div>
      </section>

      <SurfaceCard title="Role Input" subtitle={`Backend: ${BACKEND_URL}`}>
        <form className="form-grid" onSubmit={createRoleAndFetch}>
          <label className="field">
            Role title
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label className="field">
            Location
            <input value={location} onChange={(event) => setLocation(event.target.value)} />
          </label>
          <label className="field">
            Headcount
            <input
              type="number"
              min={1}
              value={headcount}
              onChange={(event) => setHeadcount(event.target.value)}
            />
          </label>
          <label className="field field-span-2">
            Must-have skills (comma separated)
            <input value={skills} onChange={(event) => setSkills(event.target.value)} />
          </label>
          <label className="field field-span-2">
            Role description
            <textarea
              rows={4}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional role context for better ranking"
            />
          </label>
          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? "Submitting…" : "Create Role + Fetch Matches"}
          </button>
        </form>

        {roleId && <p className="success-line">Role ID: {roleId}</p>}
        {roleError && <ErrorState compact message={roleError} onRetry={() => setRoleError(null)} />}
      </SurfaceCard>

      <SurfaceCard
        title="Candidate Shortlist"
        subtitle="Ranked outputs from /roles/{id}/matches"
        actions={
          roleId ? (
            <button className="secondary-button" type="button" onClick={() => fetchMatches(roleId)}>
              Refresh Matches
            </button>
          ) : null
        }
      >
        {!roleId && <p className="muted-copy">Submit role details to generate shortlist.</p>}
        {loadingMatches && <p className="muted-copy">Loading matches…</p>}
        {matchesError && roleId && <ErrorState compact message={matchesError} onRetry={() => fetchMatches(roleId)} />}
        {!loadingMatches && !matchesError && <MatchList matches={matches} />}
      </SurfaceCard>
    </div>
  );
}
