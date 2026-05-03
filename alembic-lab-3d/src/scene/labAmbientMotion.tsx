import { useFrame } from "@react-three/fiber";
import { useMemo } from "react";
import * as THREE from "three";

type EmissiveEntry = {
  mat: THREE.MeshStandardMaterial | THREE.MeshPhysicalMaterial;
  base: number;
};

function collectEmissiveMaterials(root: THREE.Object3D): EmissiveEntry[] {
  const out: EmissiveEntry[] = [];
  root.updateMatrixWorld(true);
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || !mesh.material) return;
    const mats = Array.isArray(mesh.material)
      ? mesh.material
      : [mesh.material];
    for (const raw of mats) {
      if (!(raw instanceof THREE.MeshStandardMaterial)) continue;
      const mat = raw as THREE.MeshStandardMaterial | THREE.MeshPhysicalMaterial;
      const em = mat.emissive;
      if (!(em instanceof THREE.Color)) continue;
      if (em.r + em.g + em.b < 0.015) continue;
      const base =
        typeof mat.emissiveIntensity === "number" ? mat.emissiveIntensity : 1;
      out.push({ mat, base: Math.max(base, 1e-4) });
    }
  });
  return out;
}

/** Soft pulse on lab mesh emissive (screens, tanks, trims) — no geometry jitter. */
export function LabEmissivePulse({ root }: { root: THREE.Object3D }) {
  const entries = useMemo(() => collectEmissiveMaterials(root), [root]);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const wobble = 0.88 + 0.12 * Math.sin(t * 1.05);
    const breathe = 0.94 + 0.06 * Math.sin(t * 0.35 + 2.1);
    const k = wobble * breathe;
    for (const { mat, base } of entries) {
      mat.emissiveIntensity = base * k;
    }
  });

  return null;
}
