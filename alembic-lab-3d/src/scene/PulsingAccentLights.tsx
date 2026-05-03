import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import { BRAND } from "./brandPalette";

/**
 * Very subtle accent light drift — reads as “equipment humming”, not disco.
 */
export function PulsingAccentLights() {
  const brandRef = useRef<THREE.PointLight>(null);
  const greenRef = useRef<THREE.PointLight>(null);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const b = brandRef.current;
    const g = greenRef.current;
    if (b) b.intensity = 0.2 + 0.035 * Math.sin(t * 0.85);
    if (g) g.intensity = 0.07 + 0.025 * Math.sin(t * 1.15 + 1.3);
  });

  return (
    <>
      <pointLight
        ref={brandRef}
        color={BRAND.brand}
        position={[-9, 4, -7]}
        intensity={0.2}
        distance={44}
        decay={2}
      />
      <pointLight
        ref={greenRef}
        color={BRAND.accentGreen}
        position={[8, 2, 7]}
        intensity={0.07}
        distance={34}
        decay={2}
      />
    </>
  );
}
