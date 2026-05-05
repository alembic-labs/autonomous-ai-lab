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

/**
 * Multi-GLB pick: prefer the clip that came from the file the user labelled
 * as walk/idle (most reliable — Meshy clip names like "Take 001" don't match
 * IDLE_CLIP_KEYS / WALK_CLIP_KEYS but the file name does). Falls back to
 * name-based matching against the union of all loaded clips.
 */
function pickActionByTagOrName(
  actions: Record<string, THREE.AnimationAction | null>,
  names: readonly string[],
  tagged: Array<{ clip: THREE.AnimationClip; tag: "walk" | "idle" }>,
  desiredTag: "walk" | "idle",
  nameKeys: readonly string[]
): THREE.AnimationAction | undefined {
  // 1. file-tag match: pull the first clip that came from the matching file
  const byTag = tagged.find((t) => t.tag === desiredTag)?.clip;
  if (byTag) {
    const a = actions[byTag.name];
    if (a) return a;
  }
  // 2. fallback: name-keyword match across all clips
  return pickAction(actions, names, nameKeys);
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
  // ``slot.url`` is the rigged-mesh-+-walk GLB. ``slot.idleUrl`` is the
  // optional secondary GLB whose single clip becomes the idle animation.
  // Meshy exports both files with the same Mixamo armature (matching bone
  // names), so the idle clip binds to our cloned skeleton via three.js's
  // name-based PropertyBinding without needing SkeletonUtils.retargetClip.
  const walkGltf = useGLTF(slot.url);
  const idleGltf = useGLTF(slot.idleUrl ?? slot.url);
  const { editMode } = useLayoutEdit();

  const scene = useMemo(() => {
    // Plain scene.clone() breaks SkinnedMesh rigs: clones share/wrong skeleton → same spot + bad bounds.
    const root = SkeletonUtils.clone(walkGltf.scene);
    enableMeshShadows(root, true, true);
    fitScientistUniformHeight(root, SCIENTIST_TARGET_HEIGHT);
    if (slot.scaleMultiplier && slot.scaleMultiplier !== 1) {
      root.scale.multiplyScalar(slot.scaleMultiplier);
      snapCharacterFeetToGround(root);
    }
    return root;
  }, [slot.url, slot.scaleMultiplier, walkGltf.scene]);

  // Tag clips by source so the picker prefers walkGltf for WALKING and
  // idleGltf for IDLE even if the file's clip is named generically (Meshy
  // tends to ship Mixamo-style names like "Armature|Casual_Walk|baselayer"
  // that don't always contain "walk" / "idle" — the file source is the
  // most reliable signal).
  const tagged = useMemo(() => {
    const out: Array<{ clip: THREE.AnimationClip; tag: "walk" | "idle" }> = [];
    for (const c of walkGltf.animations ?? []) out.push({ clip: c, tag: "walk" });
    if (slot.idleUrl && idleGltf !== walkGltf) {
      for (const c of idleGltf.animations ?? []) out.push({ clip: c, tag: "idle" });
    }
    return out;
  }, [walkGltf, idleGltf, slot.idleUrl]);

  const allClips = useMemo(() => {
    const seen = new Set<THREE.AnimationClip>();
    const clips: THREE.AnimationClip[] = [];
    for (const t of tagged) {
      if (seen.has(t.clip)) continue;
      seen.add(t.clip);
      clips.push(t.clip);
    }
    return clips;
  }, [tagged]);

  const { actions, names } = useAnimations(allClips, scene);
  const idleAction = useMemo(
    () => pickActionByTagOrName(actions, names, tagged, "idle", IDLE_CLIP_KEYS),
    [actions, names, tagged]
  );
  const walkAction = useMemo(
    () => pickActionByTagOrName(actions, names, tagged, "walk", WALK_CLIP_KEYS),
    [actions, names, tagged]
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
