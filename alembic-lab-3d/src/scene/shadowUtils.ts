import * as THREE from "three";

export function enableMeshShadows(
  root: THREE.Object3D,
  cast: boolean,
  receive: boolean
) {
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.isMesh) {
      mesh.castShadow = cast;
      mesh.receiveShadow = receive;
    }
  });
}
