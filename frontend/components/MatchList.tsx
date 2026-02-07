import { asStringArray, formatNumber } from "@/lib/format";
import type { MatchData } from "@/lib/types";

interface MatchListProps {
  matches: MatchData[];
}

export function MatchList({ matches }: MatchListProps) {
  if (matches.length === 0) {
    return <p className="muted-copy">No candidates matched this role yet.</p>;
  }

  return (
    <div className="match-grid">
      {matches.map((match, index) => {
        const name = match.student_name || match.name || match.candidate_name || `Candidate ${index + 1}`;
        const score = formatNumber(match.score);
        const rationale = typeof match.rationale === "string" ? match.rationale : "No rationale available.";
        const evidence = asStringArray(match.evidence);
        const gaps = asStringArray(match.gap_flags);
        const key = String(match.student_id || match.id || index);

        return (
          <article key={key} className="match-card">
            <header className="match-card-header">
              <p className="match-name">{name}</p>
              <p className="match-score">{score}</p>
            </header>
            <p className="match-rationale">{rationale}</p>
            {evidence.length > 0 && (
              <ul className="compact-list">
                {evidence.slice(0, 3).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
            {gaps.length > 0 && <p className="line-detail">Gap flags: {gaps.join(", ")}</p>}
          </article>
        );
      })}
    </div>
  );
}
