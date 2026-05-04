import { SectionHeader } from "@/components/ui/SectionHeader";
import { getReportJsonUrl, getStructureUrl } from "@/lib/api";

interface SectionDataProps {
  foldId: number;
  hasPdb?: boolean;
  /** Solana SPL Memo transaction signature (null until committed). */
  onchainSignature?: string | null;
  /** Pre-built Solscan URL for the active network (mainnet vs devnet). */
  onchainExplorerUrl?: string | null;
  /** Legacy fallback for old folds that only stored ``onchain_hash``. */
  legacyOnchainHash?: string | null;
}

function ActionLink({
  href,
  label,
  external = false,
  download = false,
}: {
  href: string;
  label: string;
  external?: boolean;
  download?: boolean;
}) {
  return (
    <a
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noreferrer" : undefined}
      download={download}
      className="btn-bracket text-small"
    >
      <span className="text-text-muted">[</span>
      <span>{label}</span>
      <span className="text-text-muted">]</span>
    </a>
  );
}

function shorten(sig: string): string {
  if (sig.length <= 12) return sig;
  return `${sig.slice(0, 8)}…${sig.slice(-4)}`;
}

export function SectionData({
  foldId,
  hasPdb = true,
  onchainSignature,
  onchainExplorerUrl,
  legacyOnchainHash,
}: SectionDataProps) {
  // Resolve the on-chain link in a single place. Prefer the explicit
  // signature + server-built explorer URL; fall back to the legacy hash
  // (older folds that only have the original ``onchain_hash`` column).
  const sig = onchainSignature ?? legacyOnchainHash ?? null;
  const href =
    onchainExplorerUrl ??
    (sig ? `https://solscan.io/tx/${sig}` : null);

  return (
    <section className="mb-16">
      <SectionHeader index="13" title="data" />
      <div className="flex flex-wrap gap-3">
        <ActionLink
          href={getReportJsonUrl(foldId)}
          label="↓ download fold.json"
          download
        />
        {hasPdb ? (
          <ActionLink
            href={getStructureUrl(foldId)}
            label="↓ download structure.pdb"
            download
          />
        ) : (
          <span className="btn-bracket text-small text-text-subtle">
            <span className="text-text-muted">[</span>
            <span>no pdb available</span>
            <span className="text-text-muted">]</span>
          </span>
        )}
        {sig && href ? (
          <ActionLink
            href={href}
            label={`↗ on-chain · ${shorten(sig)}`}
            external
          />
        ) : (
          <span className="btn-bracket text-small text-text-subtle">
            <span className="text-text-muted">[</span>
            <span>⊘ on-chain unavailable</span>
            <span className="text-text-muted">]</span>
          </span>
        )}
        <ActionLink
          href={`https://alembic.bio/folds/${foldId}`}
          label="⎘ copy permalink"
        />
      </div>
    </section>
  );
}
