interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}

export function ErrorState({
  title = "Request failed",
  message,
  onRetry,
  compact = false
}: ErrorStateProps) {
  return (
    <div className={`error-state${compact ? " error-compact" : ""}`} role="alert">
      <p className="error-title">{title}</p>
      <p className="error-message">{message}</p>
      {onRetry && (
        <button className="ghost-button" type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
