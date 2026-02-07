"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Market Truth" },
  { href: "/student", label: "Student" },
  { href: "/employer", label: "Employer" }
];

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="brand-block">
          <p className="brand-kicker">EdgeMatch MVP</p>
          <p className="brand-title">Signal-grade hiring clarity</p>
        </div>
        <nav className="shell-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${isActive ? " nav-link-active" : ""}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <main className="shell-main">{children}</main>
    </div>
  );
}
