#!/usr/bin/env node
/**
 * Removes Next.js output + webpack filesystem cache.
 * Fixes "Cannot find module './NNN.js'" when .next and webpack cache desync.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

function rm(p) {
  if (fs.existsSync(p)) {
    fs.rmSync(p, { recursive: true, force: true });
    console.log("removed", path.relative(root, p));
  }
}

rm(path.join(root, ".next"));
rm(path.join(root, "node_modules", ".cache"));
