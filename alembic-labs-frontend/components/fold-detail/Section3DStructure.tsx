"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getStructureUrl } from "@/lib/api";

// Mol* (Mol-Star) — the academic-grade molecular viewer used by RCSB PDB.
// We load the pre-built UMD bundle from /public via <Script>, then call
// `molstar.Viewer.create(...)` exactly as the upstream embed example does.
// Bundle is ~4.8 MB minified; first fold visit pays the cost, then it is
// cached aggressively across the rest of the catalog.

interface MolstarViewer {
  loadStructureFromUrl(
    url: string,
    format: string,
    isBinary?: boolean,
    options?: Record<string, unknown>,
  ): Promise<unknown>;
  dispose(): void;
}

interface MolstarGlobal {
  Viewer: {
    create(
      target: HTMLElement | string,
      options: Record<string, unknown>,
    ): Promise<MolstarViewer>;
  };
}

declare global {
  interface Window {
    molstar?: MolstarGlobal;
  }
}

async function waitForMolstar(timeoutMs = 15000): Promise<MolstarGlobal> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const g = typeof window !== "undefined" ? window.molstar : undefined;
    if (g && typeof g.Viewer?.create === "function") return g;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("Mol* script did not load in time");
}

interface Section3DStructureProps {
  foldId: number;
  hasPdb: boolean;
}

export function Section3DStructure({ foldId, hasPdb }: Section3DStructureProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<MolstarViewer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasPdb || !containerRef.current) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    const el = containerRef.current;

    (async () => {
      try {
        const molstar = await waitForMolstar();
        if (cancelled) return;

        const viewer = await molstar.Viewer.create(el, {
          // Layout: full RCSB-style chrome — state tree on the left,
          // sequence on top, structure tools on the right.
          layoutIsExpanded: false,
          layoutShowControls: true,
          layoutShowRemoteState: false,
          layoutShowSequence: true,
          layoutShowLog: false,
          layoutShowLeftPanel: true,

          viewportShowExpand: true,
          viewportShowSelectionMode: true,
          viewportShowAnimation: true,
          viewportShowControls: true,

          // Brand-aligned dark canvas. Mol* paints the gl-viewport with this
          // exact colour; chrome panels keep their default skin.
          viewportBackgroundColor: "#0a0a0a",

          pdbProvider: "rcsb",
          emdbProvider: "rcsb",
        });
        if (cancelled) {
          try {
            viewer.dispose();
          } catch {
            /* noop */
          }
          return;
        }
        viewerRef.current = viewer;

        // Custom palette: chain A → plasma red, all subsequent chains → white.
        // Mol* applies the palette in chain order, so for typical fold PDBs
        // (peptide=A, target=B[+C…]) chain A reads red and target reads white.
        // Numbers are ColorTheme `Color` aliases (0xRRGGBB).
        const PEPTIDE_RED = 0xff3344;
        const TARGET_WHITE = 0xeeeeee;
        await viewer.loadStructureFromUrl(
          getStructureUrl(foldId),
          "pdb",
          false,
          {
            representationParams: {
              theme: {
                globalName: "chain-id",
                globalColorParams: {
                  palette: {
                    name: "colors",
                    params: {
                      list: {
                        kind: "set",
                        colors: [
                          PEPTIDE_RED,
                          TARGET_WHITE,
                          TARGET_WHITE,
                          TARGET_WHITE,
                          TARGET_WHITE,
                        ],
                      },
                    },
                  },
                  asymId: "auth",
                },
                // Use the same chain-id palette for ball-and-stick / ligand
                // carbon atoms so a single component never goes default-grey.
                carbonColor: "chain-id",
              },
            },
          },
        );
        if (cancelled) return;
        setLoading(false);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("Section3DStructure (Mol*) failed:", err);
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "viewer failed to load");
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (viewerRef.current) {
        try {
          viewerRef.current.dispose();
        } catch {
          /* noop */
        }
        viewerRef.current = null;
      }
      // Mol* renders its full DOM tree inside the container — wipe it so
      // the next mount can start clean (HMR / route changes).
      el.innerHTML = "";
    };
  }, [foldId, hasPdb]);

  return (
    <section className="mb-16">
      {/* Mol* needs both its CSS and the UMD bundle — both pinned in /public. */}
      {/* eslint-disable-next-line @next/next/no-css-tags */}
      <link rel="stylesheet" href="/molstar.css" />
      <Script src="/molstar.js" strategy="afterInteractive" />

      <SectionHeader index="01" title="3D structure" />
      <div className="border border-border-subtle bg-bg-surface relative overflow-hidden">
        <div
          ref={containerRef}
          className="molstar-host relative w-full"
          style={{ minHeight: 600, height: "75vh", maxHeight: 900 }}
        />

        {!hasPdb ? (
          <div
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
            aria-live="polite"
          >
            <div className="text-center">
              <p className="text-text-muted text-small italic">
                {`// no structure on file`}
              </p>
              <p className="mt-2 text-text-subtle text-[11px] uppercase tracking-wider">
                pdb file not produced for this fold
              </p>
            </div>
          </div>
        ) : null}

        {hasPdb && loading ? (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none bg-bg-surface/60">
            <p className="text-text-muted text-small italic blink-cursor">
              {`// booting Mol* viewer`}
            </p>
          </div>
        ) : null}

        {hasPdb && error ? (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <p className="text-text-muted text-small italic">
              {`// viewer error: ${error}`}
            </p>
          </div>
        ) : null}
      </div>

      <p className="mt-3 text-text-muted text-small">
        {`// powered by Mol* — drag to rotate · scroll to zoom · `}
        <span className="text-text-secondary">use the right panel</span>
        {` for cartoon / spacefill / surface presets, measurements & export`}
      </p>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-text-muted text-small">
        <span>
          <span
            className="inline-block w-2 h-2 align-middle mr-2"
            style={{ background: "#ff3344" }}
          />
          chain A — peptide (plasma red)
        </span>
        <span>
          <span
            className="inline-block w-2 h-2 align-middle mr-2"
            style={{ background: "#eeeeee" }}
          />
          chain B+ — target / context (white)
        </span>
      </div>

      <style jsx global>{`
        .molstar-host {
          /* Mol* draws fullscreen chrome inside this box. Keep its own
             positioning context so the React loading overlay floats on top. */
          position: relative;
        }
        /* Mol* default skin renders icon buttons in the "off" state with
           color #9c835f, which sits at ~2.5:1 against the panel background
           and is barely legible. Force the resting icon color to the same
           dark brown Mol* uses for primary text, keeping the orange hover
           tint as the feedback channel. SVGs inherit currentColor so a
           single color override repaints every glyph. */
        .molstar-host .msp-plugin .msp-btn-link-toggle-off,
        .molstar-host .msp-plugin .msp-btn-link-toggle-off:active,
        .molstar-host .msp-plugin .msp-btn-link-toggle-off:focus,
        .molstar-host .msp-plugin .msp-btn-icon,
        .molstar-host .msp-plugin .msp-btn-icon-small,
        .molstar-host .msp-plugin .msp-viewport-controls-buttons .msp-btn-link,
        .molstar-host .msp-plugin .msp-viewport-controls-buttons
          .msp-btn-link-toggle-off,
        .molstar-host .msp-plugin .msp-left-panel-controls-buttons
          .msp-btn-link {
          color: #2a2218 !important;
        }
        .molstar-host .msp-plugin .msp-btn-link-toggle-off:hover,
        .molstar-host .msp-plugin .msp-btn-icon:hover,
        .molstar-host .msp-plugin .msp-btn-icon-small:hover,
        .molstar-host .msp-plugin .msp-viewport-controls-buttons
          .msp-btn-link:hover {
          color: #ff3344 !important;
        }
        /* Disabled buttons must stay visibly disabled — keep Mol*'s muted
           tone but override the !important above so we don't accidentally
           promote them. */
        .molstar-host .msp-plugin .msp-btn-icon[disabled],
        .molstar-host .msp-plugin .msp-btn-icon[disabled]:hover,
        .molstar-host .msp-plugin .msp-btn-icon-small[disabled],
        .molstar-host .msp-plugin .msp-btn-icon-small[disabled]:hover {
          color: #9c835f !important;
          opacity: 0.6;
        }
      `}</style>
    </section>
  );
}
