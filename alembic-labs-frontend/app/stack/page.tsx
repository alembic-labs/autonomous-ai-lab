import { StackChat } from "@/components/stack/StackChat";

export default function StackPage() {
  return (
    <div>
      <h1 className="text-h1 sm:text-display font-bold uppercase tracking-wider">
        stack analyzer
      </h1>
      <p className="mt-3 text-text-secondary text-body max-w-2xl leading-relaxed">
        submit your peptide stack. get analyzed for synergies, conflicts,
        mechanism overlap, and optimization. AI-powered, grounded in research
        from the lab. in silico analysis. not medical advice.
      </p>

      <hr className="my-10 border-border-subtle" />

      <StackChat />
    </div>
  );
}
