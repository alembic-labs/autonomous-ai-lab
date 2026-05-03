interface DividerProps {
  className?: string;
  variant?: "subtle" | "accent" | "dashed";
}

export function Divider({ className = "", variant = "subtle" }: DividerProps) {
  const color =
    variant === "accent"
      ? "border-border-accent"
      : variant === "dashed"
        ? "border-border-subtle border-dashed"
        : "border-border-subtle";
  return <hr className={`border-t ${color} ${className}`} />;
}
