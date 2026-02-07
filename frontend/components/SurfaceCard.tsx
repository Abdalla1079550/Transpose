import type { ReactNode } from "react";

interface SurfaceCardProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export function SurfaceCard({ title, subtitle, actions, children }: SurfaceCardProps) {
  return (
    <section className="surface-card">
      {(title || subtitle || actions) && (
        <header className="surface-card-header">
          <div>
            {title && <h2 className="surface-title">{title}</h2>}
            {subtitle && <p className="surface-subtitle">{subtitle}</p>}
          </div>
          {actions && <div className="surface-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
