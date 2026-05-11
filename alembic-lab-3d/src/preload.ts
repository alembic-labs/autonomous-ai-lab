import { useEffect, useRef, useState } from "react";

import { LAB_GLB, SCIENTISTS } from "./scene/labSceneConfig";

/**
 * Real, byte-level progress for the lab's heavy assets.
 *
 * drei's ``useProgress`` reports ``itemsLoaded / itemsTotal`` — useless
 * here because the lab GLB alone is ~60 MB (one item out of ~11), so
 * the bar sits at 0% for ~80% of the wait. Instead we stream-fetch the
 * known assets ourselves using the Fetch streams API, sum bytes across
 * all in-flight downloads, and emit a smooth percentage.
 *
 * Because we let the browser cache the responses (no ``cache: no-store``)
 * the subsequent ``useGLTF`` calls inside the Canvas hit the HTTP cache
 * instead of re-downloading the same files.
 */

export interface PreloadProgress {
  /** Total bytes fully buffered so far across every asset. */
  loaded: number;
  /** Sum of Content-Length headers; 0 until HEAD probes complete. */
  total: number;
  /** ``loaded / total`` × 100. Falls back to asset-count progress
   *  while ``total`` is still 0 so the bar always moves. */
  progress: number;
  /** All assets finished (or the fetch surface gave up retrying). */
  done: boolean;
  /** Number of fully-finished assets. */
  assetsDone: number;
  /** Number of assets we attempted to preload. */
  assetsTotal: number;
  /** Last URL that started downloading (filename for the loader UI). */
  currentItem: string;
  /** URLs whose body has finished streaming. The loader uses this to
   *  fade the moment the lab GLB lands, even if the scientist GLBs are
   *  still in flight (they show up via per-actor Suspense boundaries). */
  finishedUrls: Set<string>;
}

const INITIAL: PreloadProgress = {
  loaded: 0,
  total: 0,
  progress: 0,
  done: false,
  assetsDone: 0,
  assetsTotal: 0,
  currentItem: "",
  finishedUrls: new Set<string>(),
};

/**
 * Build the list of URLs we want to byte-stream up-front. Order matters
 * for the "currentItem" UI (the lab shell shows first), but the actual
 * downloads run in parallel via ``Promise.all``.
 */
export function getPreloadUrls(): string[] {
  const urls = new Set<string>();
  urls.add(LAB_GLB);
  for (const s of SCIENTISTS) {
    urls.add(s.url);
    if (s.idleUrl) urls.add(s.idleUrl);
  }
  return Array.from(urls);
}

async function probeSize(url: string, signal: AbortSignal): Promise<number> {
  // Try HEAD first (cheap), fall back to a Range request that fetches a
  // single byte just to peek at Content-Length. Some CDNs/proxies don't
  // honour HEAD — Caddy + nginx in our stack do, but we keep the fallback
  // so the bar still shows total bytes if someone re-deploys behind a
  // less cooperative edge.
  try {
    const r = await fetch(url, { method: "HEAD", signal });
    const len = Number(r.headers.get("content-length") || 0);
    if (len > 0) return len;
  } catch {
    // fall through
  }
  try {
    const r = await fetch(url, {
      headers: { Range: "bytes=0-0" },
      signal,
    });
    // Content-Range looks like "bytes 0-0/12345"
    const cr = r.headers.get("content-range");
    if (cr) {
      const total = Number(cr.split("/").pop() || 0);
      if (total > 0) return total;
    }
  } catch {
    // fall through
  }
  return 0;
}

export function useAssetPreload(urls: string[]): PreloadProgress {
  const [state, setState] = useState<PreloadProgress>({
    ...INITIAL,
    assetsTotal: urls.length,
  });

  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    const ctl = new AbortController();
    let cancelled = false;

    // Per-asset loaded byte counters so we can sum the in-flight bytes
    // across parallel streams without any single fetcher having to know
    // about its siblings.
    const loadedPerUrl = new Map<string, number>(urls.map((u) => [u, 0]));
    const sizePerUrl = new Map<string, number>();
    const finishedUrls = new Set<string>();
    let assetsDone = 0;

    const recompute = (currentItem?: string) => {
      if (cancelled) return;
      let loaded = 0;
      let total = 0;
      for (const u of urls) {
        loaded += loadedPerUrl.get(u) || 0;
        total += sizePerUrl.get(u) || 0;
      }
      // If the HEAD probes haven't returned yet, fall back to a coarse
      // asset-count estimate so the bar still moves a little.
      let progress: number;
      if (total > 0) {
        progress = Math.min(100, (loaded / total) * 100);
      } else {
        progress = (assetsDone / Math.max(urls.length, 1)) * 100;
      }
      setState((prev) => ({
        ...prev,
        loaded,
        total,
        progress,
        assetsDone,
        assetsTotal: urls.length,
        currentItem: currentItem ?? prev.currentItem,
        // New Set instance so React notices the reference change.
        finishedUrls: new Set(finishedUrls),
      }));
    };

    (async () => {
      // Kick off all HEAD probes in parallel — they're cheap (no body)
      // and we need the totals as soon as possible to render real %.
      void Promise.all(
        urls.map(async (u) => {
          const size = await probeSize(u, ctl.signal);
          if (cancelled) return;
          sizePerUrl.set(u, size);
          recompute();
        }),
      );

      // Now stream every body. We don't gate fetches on the HEAD probe
      // returning — the browser's HTTP/2 multiplexing handles dozens of
      // concurrent streams comfortably, and the HEAD/GET race is harmless.
      await Promise.all(
        urls.map(async (url) => {
          try {
            const res = await fetch(url, { signal: ctl.signal });
            if (!res.ok) {
              loadedPerUrl.set(url, sizePerUrl.get(url) || 0);
              assetsDone += 1;
              finishedUrls.add(url);
              recompute(url);
              return;
            }
            // If we don't have a HEAD-derived total yet, take it from
            // the GET response immediately — Content-Length is set on
            // every plain nginx response.
            const lenHeader = Number(res.headers.get("content-length") || 0);
            if (lenHeader > 0 && !sizePerUrl.get(url)) {
              sizePerUrl.set(url, lenHeader);
            }

            recompute(url);

            const reader = res.body?.getReader();
            if (!reader) {
              // Browser doesn't expose a stream — fall back to buffering
              // the whole thing. We still get cache-fill behaviour.
              const buf = await res.arrayBuffer();
              loadedPerUrl.set(url, buf.byteLength);
              assetsDone += 1;
              finishedUrls.add(url);
              recompute(url);
              return;
            }

            let assetLoaded = 0;
            // eslint-disable-next-line no-constant-condition
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              assetLoaded += value?.byteLength ?? 0;
              loadedPerUrl.set(url, assetLoaded);
              recompute(url);
            }
            assetsDone += 1;
            finishedUrls.add(url);
            // Final reconcile in case Content-Length under-reported (gzip).
            recompute(url);
          } catch (err) {
            if ((err as { name?: string })?.name === "AbortError") return;
            // Mark this asset as done so the bar can still finish — the
            // canvas's GLTFLoader will surface the real error if the
            // file is genuinely missing.
            loadedPerUrl.set(url, sizePerUrl.get(url) || 0);
            assetsDone += 1;
            finishedUrls.add(url);
            recompute();
          }
        }),
      );

      if (!cancelled) {
        setState((prev) => ({ ...prev, done: true, progress: 100 }));
      }
    })();

    return () => {
      cancelled = true;
      ctl.abort();
    };
  }, [urls]);

  return state;
}
