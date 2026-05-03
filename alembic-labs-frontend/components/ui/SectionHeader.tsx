import type { ReactNode } from "react";

interface SectionHeaderProps {
  index: string; // e.g. "01"
  title: string;
  trailing?: ReactNode;
  className?: string;
}

export function SectionHeader({ index, title, trailing, className = "" }: SectionHeaderProps) {
  return (
    <div className={`section-header ${className}`}>
      <span className="section-header__index">{index}/</span>
      <h2 className="section-header__title flex-1">{title}</h2>
      {trailing ? <div className="text-small text-text-secondary">{trailing}</div> : null}
    </div>
  );
}
