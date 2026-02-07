import { asStringArray, formatNumber } from "@/lib/format";
import type { CandidateCardData } from "@/lib/types";

interface CandidateCardProps {
  card: CandidateCardData;
}

export function CandidateCard({ card }: CandidateCardProps) {
  const name = card.full_name || card.candidate_name || card.name || "Unnamed candidate";
  const role = card.target_role || card.role || "Role pending";
  const location = typeof card.location === "string" ? card.location : "Location pending";
  const score = formatNumber(card.score);
  const summary = typeof card.summary === "string" ? card.summary : undefined;
  const rationale = typeof card.rationale === "string" ? card.rationale : undefined;
  const strengths = asStringArray(card.strengths);
  const skills = asStringArray(card.skills);

  return (
    <article className="candidate-card">
      <header className="candidate-header">
        <div>
          <p className="candidate-name">{name}</p>
          <p className="candidate-meta">
            {role} · {location}
          </p>
        </div>
        <p className="candidate-score">{score}</p>
      </header>

      {summary && <p className="candidate-summary">{summary}</p>}
      {rationale && <p className="candidate-rationale">{rationale}</p>}

      {skills.length > 0 && (
        <div className="chip-row">
          {skills.map((skill) => (
            <span key={skill} className="chip">
              {skill}
            </span>
          ))}
        </div>
      )}

      {strengths.length > 0 && (
        <ul className="compact-list">
          {strengths.slice(0, 3).map((strength) => (
            <li key={strength}>{strength}</li>
          ))}
        </ul>
      )}
    </article>
  );
}
