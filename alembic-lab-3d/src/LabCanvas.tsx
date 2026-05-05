"use client";

import { Suspense, useEffect } from "react";
import * as THREE from "three";
import { Canvas, useThree } from "@react-three/fiber";
import { Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { useLayoutEdit } from "./layoutEdit";
import { useAgentLive } from "./agents/agentLive";
import { BRAND } from "./scene/brandPalette";
import { LAB_GLB, SCIENTISTS } from "./scene/labSceneConfig";
import { LabSceneContent } from "./scene/LabScene";
import { CameraDirector } from "./scene/CameraDirector";
import { PulsingAccentLights } from "./scene/PulsingAccentLights";

/**
 * Static-shadow optimization: scientists no longer cast shadows
 * (skinned shadow casting was the heaviest GPU cost), so the only
 * shadow caster left is the lab GLB — which never moves. We let three.js
 * render the shadow map for the first second of the session (so the GLB
 * has a chance to fully load and populate the shadow buffer), then lock
 * it. Static geometry → the shadow stays valid forever, and the shadow
 * pass is skipped on every subsequent frame.
 */
function StaticShadowMap() {
  const { gl } = useThree();
  useEffect(() => {
    const t = window.setTimeout(() => {
      gl.shadowMap.autoUpdate = false;
    }, 1000);
    return () => {
      window.clearTimeout(t);
      // Restore default in case the canvas re-mounts (HMR).
      gl.shadowMap.autoUpdate = true;
    };
  }, [gl]);
  return null;
}

// Initial camera state. After mount the CameraDirector takes over and
// drives a gentle left/right pendulum (clamped to the band where the
// lab GLB actually has interior textures) plus a focus fly-in when the
// user clicks an agent. Target / initial pos are kept in rough agreement
// with the director's AMBIENT_TARGET so the first frame doesn't snap.
const CAMERA_TARGET: [number, number, number] = [3.5, 1.4, -2.2];
const CAMERA_INITIAL_POS: [number, number, number] = [3.5, 3.0, 3.6];

export function LabCanvas() {
  const { orbitRef, editMode } = useLayoutEdit();
  const { setSelectedSlotId } = useAgentLive();

  useEffect(() => {
    void useGLTF.preload(LAB_GLB);
    for (const s of SCIENTISTS) {
      void useGLTF.preload(s.url);
      if (s.idleUrl) void useGLTF.preload(s.idleUrl);
    }
  }, []);

  return (
    <Canvas
      style={{ width: "100%", height: "100%", display: "block" }}
      shadows
      camera={{
        position: CAMERA_INITIAL_POS,
        fov: 50,
        near: 0.05,
        far: 200,
      }}
      // Cap device pixel ratio at 1.5 — Retina at 2× quadruples fragment
      // shader cost (≈ 4 megapixels at 1080p × 2) and was the dominant
      // perf hit on the user's macbook. 1.5 keeps text & geometry crisp
      // without that quadrupling.
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      // Pause rendering when the canvas isn't visible (off-screen tab,
      // panel collapsed). React-three-fiber re-syncs once the user
      // returns, but we save a lot of GPU when the tab is hidden.
      performance={{ min: 0.5 }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.06;
        gl.outputColorSpace = THREE.SRGBColorSpace;
        gl.shadowMap.enabled = true;
        gl.shadowMap.type = THREE.PCFSoftShadowMap;
      }}
      // Click on empty canvas (not on any agent) clears the selection
      // panel. Edit mode handles its own clicks via TransformControls.
      onPointerMissed={() => {
        if (!editMode) setSelectedSlotId(null);
      }}
    >
      <color attach="background" args={[BRAND.bgSurface]} />
      <fog attach="fog" args={[BRAND.bgElevated, 10, 42]} />

      <ambientLight color={BRAND.textSecondary} intensity={0.2} />
      <hemisphereLight args={[BRAND.textPrimary, BRAND.borderSubtle, 0.36]} />

      <directionalLight
        color="#f4f0f2"
        position={[12, 20, 9]}
        intensity={1.02}
        castShadow
        // Down from 2048² — 1024² halves shadow-map fill rate at no
        // visible cost on a stage this small (≈12u footprint).
        shadow-mapSize={[1024, 1024]}
        shadow-bias={-0.00022}
        shadow-normalBias={0.025}
        // Tightened from ±16 (32u) to ±12 (24u) — the lab footprint is
        // ~12u and slot anchors all sit inside ±10. Tighter frustum
        // means more shadow-map texels per world unit, so 1024² here
        // ≈ 2048² over the old frustum. Free quality.
        shadow-camera-far={40}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
      />

      <PulsingAccentLights />

      <directionalLight
        color={BRAND.brandGlow}
        position={[-11, 12, -5]}
        intensity={0.18}
      />

      <Suspense fallback={null}>
        <LabSceneContent />
        <Environment
          preset="warehouse"
          environmentIntensity={0.26}
          environmentRotation={[0, 0.32, 0]}
        />
        <StaticShadowMap />
      </Suspense>

      <OrbitControls
        ref={orbitRef as never}
        makeDefault
        target={CAMERA_TARGET}
        // Constrain pitch so the camera stays in the "interior look"
        // band — no roof-cam, no looking up at the ceiling.
        minPolarAngle={Math.PI * 0.28}
        maxPolarAngle={Math.PI / 2.05}
        minDistance={2.0}
        // Cap zoom-out so the user can't drift outside the building
        // and end up staring at the back of the GLB.
        maxDistance={10}
        enablePan
        // Clamp horizontal rotation to the angles where the lab GLB has
        // interior textures — beyond ±60° you start looking through the
        // back of the building. Combined with the CameraDirector's
        // pendulum (±22°) this means manual orbit also stays "inside".
        minAzimuthAngle={-Math.PI / 3}
        maxAzimuthAngle={Math.PI / 3}
        enableDamping
      />
      <CameraDirector controlsRef={orbitRef} />
    </Canvas>
  );
}
