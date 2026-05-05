"use client";

import { Suspense, useEffect } from "react";
import * as THREE from "three";
import { Canvas } from "@react-three/fiber";
import { Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { useLayoutEdit } from "./layoutEdit";
import { BRAND } from "./scene/brandPalette";
import { LAB_GLB, SCIENTISTS } from "./scene/labSceneConfig";
import { LabSceneContent } from "./scene/LabScene";
import { PulsingAccentLights } from "./scene/PulsingAccentLights";

export function LabCanvas() {
  const { orbitRef } = useLayoutEdit();

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
      camera={{ position: [9, 6.2, 9], fov: 40, near: 0.05, far: 200 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: false }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.06;
        gl.outputColorSpace = THREE.SRGBColorSpace;
        gl.shadowMap.enabled = true;
        gl.shadowMap.type = THREE.PCFSoftShadowMap;
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
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.00022}
        shadow-normalBias={0.025}
        shadow-camera-far={56}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={16}
        shadow-camera-bottom={-16}
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
      </Suspense>

      <OrbitControls
        ref={orbitRef as never}
        makeDefault
        target={[0, 0.95, 0]}
        minPolarAngle={0.2}
        maxPolarAngle={Math.PI / 2.02}
        minDistance={2}
        maxDistance={32}
        enablePan
      />
    </Canvas>
  );
}
