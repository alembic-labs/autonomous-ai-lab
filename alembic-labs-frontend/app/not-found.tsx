import { LinkButton } from "@/components/ui/Button";
import { HermeticSymbol } from "@/components/ui/HermeticSymbol";

export default function NotFound() {
  return (
    <div className="py-24 flex flex-col items-center text-center gap-6">
      <p className="text-display font-bold tracking-wider">404</p>
      <HermeticSymbol glyph="☿" muted={false} className="text-3xl" />
      <p className="text-text-secondary">the requested fold does not exist</p>
      <LinkButton href="/">return to lab</LinkButton>
    </div>
  );
}
