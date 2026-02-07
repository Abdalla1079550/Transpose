interface MetricTileProps {
  label: string;
  value: string;
  hint?: string;
}

export function MetricTile({ label, value, hint }: MetricTileProps) {
  return (
    <article className="metric-tile">
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      {hint && <p className="metric-hint">{hint}</p>}
    </article>
  );
}
