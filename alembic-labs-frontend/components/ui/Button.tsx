import Link from "next/link";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

interface ButtonBaseProps {
  children: ReactNode;
  variant?: "bracket" | "ghost";
  size?: "md" | "sm";
  className?: string;
}

type ButtonProps = ButtonBaseProps & ComponentPropsWithoutRef<"button">;

function classes(
  variant: "bracket" | "ghost" = "bracket",
  size: "md" | "sm" = "md",
  extra = "",
): string {
  const base =
    variant === "bracket"
      ? "btn-bracket"
      : "inline-flex items-center gap-2 text-text-secondary hover:text-brand transition-colors uppercase tracking-wider";
  const sizing =
    size === "sm" ? "px-3 py-1.5 text-small" : "text-small";
  return `${base} ${sizing} ${extra}`.trim();
}

export function Button({
  children,
  variant = "bracket",
  size = "md",
  className,
  ...rest
}: ButtonProps) {
  return (
    <button {...rest} className={classes(variant, size, className)}>
      <span className="text-text-muted">[</span>
      <span>{children}</span>
      <span className="text-text-muted">]</span>
    </button>
  );
}

interface LinkButtonProps extends ButtonBaseProps {
  href: string;
  external?: boolean;
}

export function LinkButton({
  href,
  external = false,
  variant = "bracket",
  size = "md",
  className,
  children,
}: LinkButtonProps) {
  const cls = classes(variant, size, className);
  const inner = (
    <>
      <span className="text-text-muted">[</span>
      <span>{children}</span>
      <span className="text-text-muted">]</span>
    </>
  );
  if (external || href.startsWith("http")) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={cls}>
        {inner}
      </a>
    );
  }
  return (
    <Link href={href} className={cls}>
      {inner}
    </Link>
  );
}
