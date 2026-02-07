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
        const name = match.name || match.candidate_name || `Candidate ${index + 1}`;
        const score = formatNumber(match.score);
        const rationale = typeof match.rationale === "string" ? match.rationale : "No rationale available.";
        const skills = asStringArray(match.skills);
        const key = String(match.student_id || match.id || index);

        return (
          <article key={key} className="match-card">
            <header className="match-card-header">
              <p className="match-name">{name}</p>
              <p className="match-score">{score}</p>
            </header>
            <p className="match-rationale">{rationale}</p>
            {skills.length > 0 && (
              <div className="chip-row">
                {skills.slice(0, 5).map((skill) => (
                  <span key={skill} className="chip">
                    {skill}
                  </span>
                ))}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
