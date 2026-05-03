"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Wordmark } from "./Wordmark";

const NAV_LINKS = [
  { href: "/", label: "HOME" },
  { href: "/folds", label: "FOLDS" },
  { href: "/lab", label: "LAB" },
  { href: "/stack", label: "STACK" },
  { href: "/about", label: "ABOUT" },
];

export function TopNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname?.startsWith(href);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border-subtle bg-bg/90 backdrop-blur supports-[backdrop-filter]:bg-bg/70">
      <div className="container-content flex items-center gap-6 py-3">
        <Wordmark size="md" />

        <nav className="hidden md:flex items-center gap-1 ml-auto">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`px-3 py-1.5 text-small uppercase tracking-wider transition-colors ${
                isActive(link.href)
                  ? "text-brand"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto md:ml-0 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="md:hidden text-text-secondary hover:text-brand text-small uppercase tracking-wider px-2 py-1 border border-border-accent"
            aria-label="Toggle navigation"
          >
            {open ? "CLOSE" : "MENU"}
          </button>
        </div>
      </div>

      {open ? (
        <div className="md:hidden border-t border-border-subtle bg-bg-surface">
          <div className="container-content flex flex-col py-2">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={`py-2 text-small uppercase tracking-wider ${
                  isActive(link.href) ? "text-brand" : "text-text-secondary"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </header>
  );
}
