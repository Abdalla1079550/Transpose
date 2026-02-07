import { asStringArray, formatNumber } from "@/lib/format";
import type { CandidateCardData } from "@/lib/types";

interface CandidateCardProps {
  card: CandidateCardData;
}

export function CandidateCard({ card }: CandidateCardProps) {
  const nestedCandidate = card.candidate || {};
  const name =
    nestedCandidate.name || card.full_name || card.candidate_name || card.name || "Unnamed candidate";
  const roleFit = asStringArray(card.role_fit_suggestions);
  const topSkills = asStringArray(card.normalized_skill_list).slice(0, 15);
  const strengths = asStringArray(card.strengths);
  const gaps = asStringArray(card.gaps);
  const improvements = asStringArray(card.improvements);
  const marketTop = asStringArray(card.market_context?.top_market_skills);

  const region =
    nestedCandidate.region_pref ||
    (card.market_context && typeof card.market_context.region === "string" ? card.market_context.region : "N/A");
  const gradYear = nestedCandidate.grad_year || card.grad_year || "N/A";
  const hiringNow = card.market_context?.hiring_now_estimate;
  const citation = card.market_context?.citation;

  return (
    <article className="candidate-card">
      <header className="candidate-header">
        <div>
          <p className="candidate-name">{name}</p>
          <p className="candidate-meta">
            Region {region} · Grad {String(gradYear)}
          </p>
        </div>
        <p className="candidate-score">{formatNumber(hiringNow)}</p>
      </header>

      {roleFit.length > 0 && <p className="candidate-summary">Role fit: {roleFit.slice(0, 5).join(", ")}</p>}
      {citation && <p className="candidate-rationale">{citation}</p>}

      {topSkills.length > 0 && (
        <div className="chip-row">
          {topSkills.map((skill) => (
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

      {gaps.length > 0 && (
        <ul className="compact-list">
          {gaps.slice(0, 3).map((gap) => (
            <li key={gap}>{gap}</li>
          ))}
        </ul>
      )}

      {improvements.length > 0 && (
        <ul className="compact-list">
          {improvements.slice(0, 3).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}

      {marketTop.length > 0 && (
        <p className="candidate-meta">Market top skills: {marketTop.slice(0, 5).join(", ")}</p>
      )}
    </article>
  );
}
