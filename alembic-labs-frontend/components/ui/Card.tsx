import Link from "next/link";
import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  href?: string;
}

export function Card({ children, className = "", interactive = false, href }: CardProps) {
  const cls = `card ${interactive ? "card--interactive" : ""} ${className}`.trim();
  if (href) {
    return (
      <Link href={href} className={`${cls} block`}>
        {children}
      </Link>
    );
  }
  return <div className={cls}>{children}</div>;
}
