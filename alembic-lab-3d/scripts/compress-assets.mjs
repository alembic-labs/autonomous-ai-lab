#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * GLB compression pipeline for /public/3d-lab.
 *
 * Source GLBs (uncompressed Meshy / Sketchfab exports) live in
 *   ./public/3d-lab-source
 * Compressed runtime GLBs (committed + served by nginx) live in
 *   ./public/3d-lab
 *
 * The pipeline:
 *   1. dedup   — collapse duplicate accessors / textures / materials.
 *   2. resize  — clamp every texture to a max dimension.
 *   3. webp    — re-encode PNG → WebP at q=78 (lab) / q=82 (scientists).
 *   4. meshopt — vertex attribute compression + KHR_mesh_quantization.
 *
 * Drei's `useGLTF` auto-installs MeshoptDecoder via three-stdlib and
 * three.js parses WebP textures natively, so no frontend changes are
 * required.
 *
 * Run with:  npm run compress-assets
 * Or:        node scripts/compress-assets.mjs
 */

import { mkdir, readdir, rm, stat, copyFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import {
  dedup,
  meshopt,
  prune,
  reorder,
  resample,
  textureCompress,
} from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const SRC_DIR = path.join(ROOT, "public", "3d-lab-source");
const OUT_DIR = path.join(ROOT, "public", "3d-lab");

/** Per-file compression knobs. Lab textures get the most aggressive
 *  resize because the sci-fi_lab.glb pulls in 60+ identical-resolution
 *  PBR textures that dominate the asset weight. Scientist textures are
 *  fewer per file and viewed up close, so we keep them at 1024. */
const PRESETS = {
  default: { maxSize: 1024, quality: 82 },
  "sci-fi_lab.glb": { maxSize: 512, quality: 78 },
};

function fmtMb(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(2)} mb`;
}

async function ensureDir(dir) {
  await mkdir(dir, { recursive: true });
}

async function compressOne(io, srcPath, dstPath, preset) {
  const srcStat = await stat(srcPath);
  const doc = await io.read(srcPath);

  await doc.transform(
    dedup(),
    // Drop unused accessors / nodes / materials before doing expensive
    // work — Meshy exports often include bind-pose duplicates.
    prune(),
    // Resample animations to drop redundant keyframes (idle clips often
    // ship with 60 fps tracks that are perfectly straight).
    resample(),
    // Resize every texture before re-encoding to webp. sharp is the
    // only cross-platform image backend that handles 16-bit normals
    // without artefacts.
    textureCompress({
      encoder: sharp,
      targetFormat: "webp",
      resize: [preset.maxSize, preset.maxSize],
      quality: preset.quality,
      effort: 6,
    }),
    // Reorder vertex/index streams for better compression ratios.
    reorder({ encoder: MeshoptEncoder }),
    // EXT_meshopt_compression — drei + three-stdlib decode this natively.
    meshopt({ encoder: MeshoptEncoder, level: "high" }),
  );

  await io.write(dstPath, doc);
  const dstStat = await stat(dstPath);
  return { src: srcStat.size, dst: dstStat.size };
}

async function main() {
  let entries;
  try {
    entries = await readdir(SRC_DIR);
  } catch (err) {
    if (err.code === "ENOENT") {
      console.error(`source folder not found: ${SRC_DIR}`);
      console.error(
        "Drop the original Meshy / Sketchfab GLBs into public/3d-lab-source/ and re-run.",
      );
      process.exit(1);
    }
    throw err;
  }

  const glbs = entries.filter((f) => f.toLowerCase().endsWith(".glb"));
  if (glbs.length === 0) {
    console.error(`no GLBs found in ${SRC_DIR}`);
    process.exit(1);
  }

  await ensureDir(OUT_DIR);

  // Pass any non-GLB siblings (lab-layout.json, etc) through untouched
  // so the runtime folder is self-contained.
  for (const file of entries) {
    if (!file.toLowerCase().endsWith(".glb") && !file.startsWith(".")) {
      await copyFile(path.join(SRC_DIR, file), path.join(OUT_DIR, file));
    }
  }

  await MeshoptEncoder.ready;
  await MeshoptDecoder.ready;

  const io = new NodeIO()
    .registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({
      "meshopt.decoder": MeshoptDecoder,
      "meshopt.encoder": MeshoptEncoder,
    });

  let totalIn = 0;
  let totalOut = 0;
  const rows = [];

  for (const file of glbs) {
    const preset = PRESETS[file] || PRESETS.default;
    const srcPath = path.join(SRC_DIR, file);
    const dstPath = path.join(OUT_DIR, file);
    process.stdout.write(`compressing ${file}…`);
    const t0 = Date.now();
    const { src, dst } = await compressOne(io, srcPath, dstPath, preset);
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    totalIn += src;
    totalOut += dst;
    const ratio = (src / dst).toFixed(1);
    process.stdout.write(
      ` ${fmtMb(src)} → ${fmtMb(dst)} (${ratio}× · ${elapsed}s)\n`,
    );
    rows.push({ file, src, dst, ratio });
  }

  console.log("\n— summary —");
  console.log(
    `total: ${fmtMb(totalIn)} → ${fmtMb(totalOut)} (${(totalIn / totalOut).toFixed(1)}× reduction)`,
  );
  console.log(`output dir: ${OUT_DIR}`);
}

main().catch((err) => {
  console.error("compression failed:", err);
  process.exit(1);
});
