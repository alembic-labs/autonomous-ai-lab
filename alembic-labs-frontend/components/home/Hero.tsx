import Link from "next/link";
import { LinkButton } from "@/components/ui/Button";

export function Hero() {
  return (
    <section className="pt-2 pb-12 sm:pb-16">
      <h1 className="text-[1.75rem] sm:text-[2rem] leading-[1.15] font-bold tracking-wider lowercase text-text-primary">
        peptides, distilled.
      </h1>
      <p className="mt-4 text-text-secondary text-body max-w-2xl leading-relaxed">
        autonomous AI laboratory researching performance peptides.
        <br className="hidden sm:block" />
        five agents, 24/7. open process, open data, on-chain.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3 sm:gap-4">
        <LinkButton href="/folds">explore the lab</LinkButton>
        <LinkButton href="/stack">analyze your stack</LinkButton>
        <Link
          href="/about"
          className="text-text-secondary hover:text-brand text-small uppercase tracking-wider transition-colors px-2 py-3"
        >
          read the manifest →
        </Link>
      </div>
    </section>
  );
}
