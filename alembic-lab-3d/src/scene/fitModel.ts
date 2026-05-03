import * as THREE from "three";

const _tmpBox = new THREE.Box3();
const _size = new THREE.Vector3();

/**
 * Raw union of all mesh bounds (room + simple assets).
 */
export function computeMeshBoundingBox(root: THREE.Object3D): THREE.Box3 {
  const box = new THREE.Box3();
  let any = false;
  root.updateMatrixWorld(true);
  root.traverse((obj) => {
    const m = obj as THREE.Mesh;
    if (!m.isMesh || !m.geometry) return;
    if (!m.geometry.boundingBox) m.geometry.computeBoundingBox();
    const bb = m.geometry.boundingBox;
    if (!bb) return;
    _tmpBox.copy(bb).applyMatrix4(m.matrixWorld);
    if (!any) {
      box.copy(_tmpBox);
      any = true;
    } else {
      box.union(_tmpBox);
    }
  });
  return box;
}

type MeshPart = { box: THREE.Box3; diag: number };

/**
 * Character GLBs often hide one enormous triangle/collision mesh — it blows up the
 * bounding box and scales the figure to a giant. Drop outlier meshes vs median size.
 */
export function computeFilteredCharacterBoundingBox(
  root: THREE.Object3D
): THREE.Box3 {
  root.updateMatrixWorld(true);
  const parts: MeshPart[] = [];

  root.traverse((obj) => {
    const m = obj as THREE.Mesh;
    if (!m.isMesh || !m.geometry) return;
    _tmpBox.setFromObject(m);
    if (_tmpBox.isEmpty()) return;
    const sz = _tmpBox.getSize(_size);
    const diag = sz.length();
    if (diag < 1e-8) return;
    parts.push({ box: _tmpBox.clone(), diag });
  });

  if (parts.length === 0) return new THREE.Box3();

  const diags = parts.map((p) => p.diag).sort((a, b) => a - b);
  const median = diags[Math.floor(diags.length / 2)]!;
  /** Keep body/clothes meshes; drop invisible hulls ~10× median or more */
  const limit = Math.max(median * 10, 0.2);

  const box = new THREE.Box3();
  let any = false;
  for (const p of parts) {
    if (p.diag > limit) continue;
    if (!any) {
      box.copy(p.box);
      any = true;
    } else box.union(p.box);
  }

  if (!any) {
    parts.sort((a, b) => a.diag - b.diag);
    return parts[0]!.box.clone();
  }
  return box;
}

/** Scale room so floor footprint max(x,z) ≈ targetMaxXZ; snap floor to y=0. */
export function fitLabFootprintGroundY(
  root: THREE.Object3D,
  targetMaxXZ: number
) {
  root.scale.set(1, 1, 1);
  root.position.set(0, 0, 0);
  root.updateMatrixWorld(true);
  let bbox = computeMeshBoundingBox(root);
  if (bbox.isEmpty()) {
    bbox = new THREE.Box3().setFromObject(root);
  }
  const size = bbox.getSize(new THREE.Vector3());
  const xz = Math.max(size.x, size.z, 1e-4);
  const s = targetMaxXZ / xz;
  root.scale.multiplyScalar(s);
  root.updateMatrixWorld(true);
  bbox = computeMeshBoundingBox(root);
  if (bbox.isEmpty()) bbox = new THREE.Box3().setFromObject(root);
  root.position.y -= bbox.min.y;
}

/**
 * Same target height for every agent; uses filtered mesh bounds so one junk hull
 * cannot scale the whole rig to a giant.
 */
export function fitScientistUniformHeight(
  root: THREE.Object3D,
  targetHeight: number
) {
  root.scale.set(1, 1, 1);
  root.position.set(0, 0, 0);
  root.updateMatrixWorld(true);

  let bbox = computeFilteredCharacterBoundingBox(root);
  if (bbox.isEmpty()) {
    bbox = computeMeshBoundingBox(root);
  }
  if (bbox.isEmpty()) {
    bbox = new THREE.Box3().setFromObject(root);
  }

  const size = bbox.getSize(new THREE.Vector3());
  const h = Math.max(size.y, 1e-4);
  let s = targetHeight / h;

  /** Filtered bbox sometimes shrinks to a button-sized hull → astronomical scale */
  if (!Number.isFinite(s) || s > 24 || s < 0.04) {
    root.scale.set(1, 1, 1);
    root.position.set(0, 0, 0);
    root.updateMatrixWorld(true);
    bbox = computeMeshBoundingBox(root);
    if (bbox.isEmpty()) bbox = new THREE.Box3().setFromObject(root);
    const sz = bbox.getSize(new THREE.Vector3());
    const h2 = Math.max(sz.y, 1e-4);
    s = targetHeight / h2;
  }
  s = THREE.MathUtils.clamp(s, 0.04, 24);

  root.scale.multiplyScalar(s);
  root.updateMatrixWorld(true);

  bbox = computeFilteredCharacterBoundingBox(root);
  if (bbox.isEmpty()) bbox = computeMeshBoundingBox(root);
  if (bbox.isEmpty()) bbox = new THREE.Box3().setFromObject(root);
  root.position.y -= bbox.min.y;
}

/** After an extra uniform scale, re-seat feet at y=0. */
export function snapCharacterFeetToGround(root: THREE.Object3D) {
  root.updateMatrixWorld(true);
  let bbox = computeFilteredCharacterBoundingBox(root);
  if (bbox.isEmpty()) bbox = computeMeshBoundingBox(root);
  if (bbox.isEmpty()) bbox = new THREE.Box3().setFromObject(root);
  root.position.y -= bbox.min.y;
}
