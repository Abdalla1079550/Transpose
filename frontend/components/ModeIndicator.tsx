import type { Mode } from "@/lib/types";

interface ModeIndicatorProps {
  mode: Mode;
}

const LABELS: Record<Mode, string> = {
  live: "LIVE",
  demo: "DEMO",
  unknown: "UNKNOWN"
};

export function ModeIndicator({ mode }: ModeIndicatorProps) {
  return (
    <span className={`mode-indicator mode-${mode}`} aria-live="polite">
      {LABELS[mode]} MODE
    </span>
  );
}
