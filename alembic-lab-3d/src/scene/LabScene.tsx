"use client";

import { useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import { SkeletonUtils } from "three-stdlib";
import {
  LAB_GLB,
  LAB_TARGET_FOOTPRINT,
  SCIENTISTS,
  SCIENTIST_TARGET_HEIGHT,
} from "./labSceneConfig";
import {
  fitLabFootprintGroundY,
  fitScientistUniformHeight,
  snapCharacterFeetToGround,
} from "./fitModel";
import { LabEmissivePulse } from "./labAmbientMotion";
import { enableMeshShadows } from "./shadowUtils";
import { TransformableAgent } from "./TransformableAgent";

function LabRoom() {
  const gltf = useGLTF(LAB_GLB);
  const scene = useMemo(() => {
    const root = gltf.scene.clone();
    enableMeshShadows(root, true, true);
    fitLabFootprintGroundY(root, LAB_TARGET_FOOTPRINT);
    return root;
  }, [gltf.scene]);
  return (
    <>
      <primitive object={scene} dispose={null} />
      <LabEmissivePulse root={scene} />
    </>
  );
}

function ScientistModel({
  url,
  scaleMultiplier = 1,
}: {
  url: string;
  scaleMultiplier?: number;
}) {
  const gltf = useGLTF(url);
  const scene = useMemo(() => {
    // Plain scene.clone() breaks SkinnedMesh rigs: clones share/wrong skeleton → same spot + bad bounds.
    const root = SkeletonUtils.clone(gltf.scene);
    enableMeshShadows(root, true, true);
    fitScientistUniformHeight(root, SCIENTIST_TARGET_HEIGHT);
    if (scaleMultiplier !== 1) {
      root.scale.multiplyScalar(scaleMultiplier);
      snapCharacterFeetToGround(root);
    }
    return root;
  }, [url, gltf.scene, scaleMultiplier]);
  return <primitive object={scene} dispose={null} />;
}

export function LabSceneContent() {
  return (
    <>
      <LabRoom />
      {SCIENTISTS.map((s) => (
        <TransformableAgent key={s.id} id={s.id}>
          <ScientistModel
            url={s.url}
            scaleMultiplier={s.scaleMultiplier}
          />
        </TransformableAgent>
      ))}
    </>
  );
}
