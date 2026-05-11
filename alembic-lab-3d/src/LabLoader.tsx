import { useEffect, useMemo, useState } from "react";

import { getPreloadUrls, useAssetPreload } from "./preload";
import { LAB_GLB } from "./scene/labSceneConfig";

/**
 * Loader overlay shown while the room GLB downloads.
 *
 * UX strategy: per-actor Suspense boundaries inside the canvas mean
 * the lab room can show up the instant ``sci-fi_lab.glb`` is parsed,
 * even while scientist GLBs are still in flight. So the loader only
 * waits for the room GLB — once that's in the HTTP cache and the
 * canvas has rendered at least one frame, we fade and the user sees
 * the populated environment with characters trickling in over the
 * next 2-3s.
 *
 * Phasing:
 *   0..98%  : byte progress for sci-fi_lab.glb (network bound)
 *   98..100%: hold so the smoothed bar visually reaches 100%
 *   fade out (420ms)
 */
export function LabLoader() {
  const urls = useMemo(() => getPreloadUrls(), []);
  const preload = useAssetPreload(urls);

  // Lab GLB byte progress, derived from the preload's per-URL stats.
  // Falls back to global progress in the rare case the lab URL HEAD
  // probe failed and we can't isolate it.
  const labReady = preload.finishedUrls.has(LAB_GLB);

  const [visible, setVisible] = useState(true);
  const [fading, setFading] = useState(false);
  const [internalDone, setInternalDone] = useState(false);

  useEffect(() => {
    if (labReady && !internalDone) {
      // Hold half a second so:
      //   1. the smoothed bar visibly reaches the high 90s before fade,
      //   2. drei's GLTFLoader has time to parse the cached bytes and
      //      the LabRoom Suspense unblocks behind the loader,
      //   3. shader compilation lands on the first frame.
      const hold = window.setTimeout(() => setInternalDone(true), 500);
      return () => window.clearTimeout(hold);
    }
    return undefined;
  }, [labReady, internalDone]);

  useEffect(() => {
    if (!internalDone) return undefined;
    setFading(true);
    const t = window.setTimeout(() => setVisible(false), 420);
    return () => window.clearTimeout(t);
  }, [internalDone]);

  // Smoothed display progress — lerp toward the byte progress every
  // frame. Uses the LAB_GLB-only progress when available (so the bar
  // hits 100% the moment the room is in cache); otherwise uses the
  // global byte progress.
  const labProgress = (() => {
    const labLoaded = preload.finishedUrls.has(LAB_GLB)
      ? 100
      : // Approximate: when the lab HEAD probe came back, we know its
        // size is tiny (~3 MB) relative to total, but we don't track
        // per-URL bytes here. Use global progress capped to 100.
        Math.min(99, preload.progress);
    return labLoaded;
  })();

  const [displayProgress, setDisplayProgress] = useState(0);
  useEffect(() => {
    let raf = 0;
    let prev = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;
      const k = 1 - Math.exp(-dt * 5);
      setDisplayProgress((cur) => cur + (labProgress - cur) * k);
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [labProgress]);

  if (!visible) return null;

  const itemLabel = preload.currentItem
    ? preload.currentItem.split("/").pop() ?? preload.currentItem
    : "lab assets";

  const totalMb = preload.total > 0 ? preload.total / 1024 / 1024 : null;
  const loadedMb = preload.loaded / 1024 / 1024;

  const barPct = Math.max(0, Math.min(100, displayProgress));

  return (
    <div
      className={`lab-loader${fading ? " lab-loader-fade" : ""}`}
      role="status"
      aria-live="polite"
    >
      <div className="lab-loader-card">
        <div className="lab-loader-mark">
          <span className="lab-loader-pulse" aria-hidden />
          <span className="lab-loader-mark-text">ALEMBIC LABS</span>
        </div>
        <div className="lab-loader-title">booting 3d laboratory</div>
        <div className="lab-loader-bar" aria-hidden>
          <div
            className="lab-loader-bar-fill"
            style={{ width: `${barPct.toFixed(1)}%` }}
          />
        </div>
        <div className="lab-loader-meta">
          <span className="lab-loader-meta-pct">{barPct.toFixed(0)}%</span>
          <span className="lab-loader-meta-sep">·</span>
          <span className="lab-loader-meta-count">
            {totalMb !== null
              ? `${loadedMb.toFixed(1)} / ${totalMb.toFixed(1)} mb`
              : `${loadedMb.toFixed(1)} mb`}
          </span>
          <span className="lab-loader-meta-sep">·</span>
          <span className="lab-loader-meta-count">
            {preload.assetsDone}/{preload.assetsTotal} files
          </span>
        </div>
        <div className="lab-loader-item" title={itemLabel}>
          {labReady
            ? "scientists materialising…"
            : `streaming · ${itemLabel}`}
        </div>
        <div className="lab-loader-hint">
          first visit downloads ~20 mb of geometry, rigs &amp; webp textures.
          <br />
          subsequent loads come from cache.
        </div>
      </div>
    </div>
  );
}
