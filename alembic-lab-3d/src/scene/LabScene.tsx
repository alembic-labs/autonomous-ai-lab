"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useAnimations, useGLTF } from "@react-three/drei";
import { SkeletonUtils } from "three-stdlib";
import {
  LAB_GLB,
  LAB_TARGET_FOOTPRINT,
  SCIENTISTS,
  SCIENTIST_TARGET_HEIGHT,
  type ScientistSlot,
} from "./labSceneConfig";
import {
  fitLabFootprintGroundY,
  fitScientistUniformHeight,
  snapCharacterFeetToGround,
} from "./fitModel";
import { LabEmissivePulse } from "./labAmbientMotion";
import { enableMeshShadows } from "./shadowUtils";
import { TransformableAgent } from "./TransformableAgent";
import { useLayoutEdit } from "../layoutEdit";
import { useWander, type WanderState } from "./useWander";

const IDLE_CLIP_KEYS = ["idle", "stand", "breathe", "rest", "wait"];
const WALK_CLIP_KEYS = ["walk", "walking", "locomotion", "move", "run"];

function pickAction(
  actions: Record<string, THREE.AnimationAction | null>,
  names: readonly string[],
  preferred: readonly string[]
): THREE.AnimationAction | undefined {
  if (!names.length) return undefined;
  const lower = names.map((n) => n.toLowerCase());
  // exact match first
  for (const p of preferred) {
    const i = lower.indexOf(p);
    if (i >= 0) return actions[names[i]] ?? undefined;
  }
  // partial match (e.g. "Walk_Loop_01" matches "walk")
  for (const p of preferred) {
    const i = lower.findIndex((n) => n.includes(p));
    if (i >= 0) return actions[names[i]] ?? undefined;
  }
  return undefined;
}

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

function ScientistModel({ slot }: { slot: ScientistSlot }) {
  const gltf = useGLTF(slot.url);
  const { editMode } = useLayoutEdit();

  const scene = useMemo(() => {
    // Plain scene.clone() breaks SkinnedMesh rigs: clones share/wrong skeleton → same spot + bad bounds.
    const root = SkeletonUtils.clone(gltf.scene);
    enableMeshShadows(root, true, true);
    fitScientistUniformHeight(root, SCIENTIST_TARGET_HEIGHT);
    if (slot.scaleMultiplier && slot.scaleMultiplier !== 1) {
      root.scale.multiplyScalar(slot.scaleMultiplier);
      snapCharacterFeetToGround(root);
    }
    return root;
  }, [slot.url, slot.scaleMultiplier, gltf.scene]);

  // Drive baked clips from the GLB (idle / walk loops) when present.
  // useAnimations creates a per-instance AnimationMixer scoped to ``scene``,
  // so each scientist plays its own clips at its own phase.
  const { actions, names } = useAnimations(gltf.animations, scene);
  const idleAction = useMemo(
    () => pickAction(actions, names, IDLE_CLIP_KEYS),
    [actions, names]
  );
  const walkAction = useMemo(
    () => pickAction(actions, names, WALK_CLIP_KEYS),
    [actions, names]
  );

  // Wandering happens on this inner group (LOCAL frame relative to anchor).
  const wanderRef = useRef<THREE.Group>(null!);
  const wanderEnabled = !editMode && slot.wandering !== false;

  // Boot into IDLE (or rest pose if no idle clip exists).
  useEffect(() => {
    idleAction?.reset().fadeIn(0.4).play();
    return () => {
      idleAction?.fadeOut(0.25);
      walkAction?.fadeOut(0.25);
    };
  }, [idleAction, walkAction]);

  const animState = useRef<WanderState>("IDLE");
  useWander(wanderRef, {
    enabled: wanderEnabled,
    tuning: slot.wander,
    onState: (next) => {
      if (next === animState.current) return;
      animState.current = next;
      if (next === "WALKING") {
        idleAction?.fadeOut(0.25);
        walkAction?.reset().fadeIn(0.25).play();
      } else {
        walkAction?.fadeOut(0.25);
        idleAction?.reset().fadeIn(0.25).play();
      }
    },
  });

  return (
    <group ref={wanderRef}>
      <primitive object={scene} dispose={null} />
    </group>
  );
}

export function LabSceneContent() {
  return (
    <>
      <LabRoom />
      {SCIENTISTS.map((s) => (
        <TransformableAgent key={s.id} id={s.id}>
          <ScientistModel slot={s} />
        </TransformableAgent>
      ))}
    </>
  );
}
