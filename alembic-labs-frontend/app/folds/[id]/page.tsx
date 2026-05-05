import { Metadata } from "next";
import { notFound } from "next/navigation";
import { FoldHeader } from "@/components/fold-detail/FoldHeader";
import { Section3DStructure } from "@/components/fold-detail/Section3DStructure";
import { SectionAIAnalysis } from "@/components/fold-detail/SectionAIAnalysis";
import { SectionResearchData } from "@/components/fold-detail/SectionResearchData";
import { SectionResearchBrief } from "@/components/fold-detail/SectionResearchBrief";
import { SectionFoldingMetrics } from "@/components/fold-detail/SectionFoldingMetrics";
import { SectionDomainAnnotations } from "@/components/fold-detail/SectionDomainAnnotations";
import { SectionStructuralCaption } from "@/components/fold-detail/SectionStructuralCaption";
import { SectionPeptideProfile } from "@/components/fold-detail/SectionPeptideProfile";
import { SectionKnownBinders } from "@/components/fold-detail/SectionKnownBinders";
import { SectionAgentFindings } from "@/components/fold-detail/SectionAgentFindings";
import { SectionCaveats } from "@/components/fold-detail/SectionCaveats";
import { SectionData } from "@/components/fold-detail/SectionData";
import { SectionWorksCited } from "@/components/fold-detail/SectionWorksCited";
import { getFold, getFoldMetrics } from "@/lib/api";
import type { FoldMetrics } from "@/lib/types";

export const dynamic = "force-dynamic";

interface FoldDetailPageProps {
  params: { id: string };
}

/**
 * Resolve the route param into something the backend can look up.
 *
 * The catch-all detail route accepts both legacy numeric ids ("/folds/12")
 * and SEO slugs ("/folds/12-sermorelin-d-ala2-substitution"). The backend
 * resolves both via the same endpoint, so we just pass the raw segment
 * straight through after a sanity check.
 */
function isValidRef(ref: string | undefined): boolean {
  if (!ref) return false;
  if (/^\d+$/.test(ref)) return true;
  // Slugs always start with a numeric prefix the backend can fall back to.
  return /^\d+-[a-z0-9-]+$/i.test(ref) && ref.length <= 200;
}

export async function generateMetadata({
  params,
}: FoldDetailPageProps): Promise<Metadata> {
  if (!isValidRef(params.id)) return { title: "DISTILLATION — ALEMBIC LABS" };
  try {
    const fold = await getFold(params.id);
    const number = `№${fold.id}`;
    const title = `DISTILLATION ${number} — ${fold.peptide_name} | ALEMBIC LABS`;
    const description =
      fold.executive_summary ||
      fold.tldr ||
      `${fold.modification_description} on ${fold.peptide_name}.`;
    const canonicalSlug = fold.slug ?? String(fold.id);
    return {
      title,
      description,
      alternates: { canonical: `/folds/${canonicalSlug}` },
      openGraph: {
        title,
        description,
        type: "article",
        url: `/folds/${canonicalSlug}`,
      },
      twitter: {
        card: "summary_large_image",
        title,
        description,
      },
    };
  } catch {
    return { title: "DISTILLATION — ALEMBIC LABS" };
  }
}

export default async function FoldDetailPage({ params }: FoldDetailPageProps) {
  if (!isValidRef(params.id)) {
    notFound();
  }

  let fold;
  try {
    fold = await getFold(params.id);
  } catch {
    notFound();
  }

  // Metrics endpoint may legitimately have no plot data (Boltz-2 sometimes
  // skips per-residue export). Don't 404 the whole page if it fails.
  let metrics: FoldMetrics | null = null;
  try {
    metrics = await getFoldMetrics(params.id);
  } catch {
    metrics = null;
  }

  const pmid = fold.works_cited?.[0]?.pmid;

  return (
    <article>
      <FoldHeader fold={fold} pmid={pmid} />

      <Section3DStructure foldId={fold.id} hasPdb={fold.has_pdb} />

      <SectionAIAnalysis
        tldr={fold.tldr}
        detailed={fold.detailed_analysis}
        discardReason={fold.discard_reason}
      />

      <SectionResearchData
        knownActivity={fold.known_activity}
        biohackerUse={fold.biohacker_use}
        mechanismClass={fold.mechanism_class}
      />

      <SectionResearchBrief
        markdown={fold.research_brief_markdown}
        executiveSummary={fold.executive_summary}
      />

      <SectionFoldingMetrics
        metrics={metrics}
        fallback={{
          plddt: fold.confidence_plddt,
          ptm: fold.confidence_ptm,
          iptm: fold.confidence_iptm,
          agreement: fold.agreement_score,
        }}
        chai1Decision={fold.chai1_gated_decision}
      />

      <SectionDomainAnnotations data={fold.domain_annotations} />

      <SectionStructuralCaption caption={fold.structural_caption} />

      <SectionPeptideProfile
        aggregation={fold.aggregation_propensity}
        stability={fold.stability_score}
        bbb={fold.bbb_penetration_score}
        halfLife={fold.half_life_estimate}
      />

      <SectionKnownBinders binders={fold.known_binders} />

      {/* 10/ Candidate Variants — intentionally skipped for now */}

      <SectionAgentFindings trace={fold.agent_trace} />

      <SectionCaveats caveats={fold.caveats} />

      <SectionData
        foldId={fold.id}
        hasPdb={fold.has_pdb}
        onchainSignature={fold.onchain_signature}
        onchainExplorerUrl={fold.onchain_explorer_url}
        legacyOnchainHash={fold.onchain_hash}
      />

      <SectionWorksCited papers={fold.works_cited ?? undefined} />
    </article>
  );
}
