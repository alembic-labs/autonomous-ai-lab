import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { SCIENTISTS } from "./labSceneConfig";
import { useLayoutEdit } from "../layoutEdit";
import { useAgentLive } from "../agents/agentLive";

// ──────────────────────────────────────────────────────────────────────
// Camera tuning. The full-rotation autoRotate that ships with
// OrbitControls swings the camera through the GLB's back wall (the lab
// is only modelled as a box, not a 360° interior) and pops behind the
// outer textures. Instead we drive the camera ourselves with a gentle
// LEFT-RIGHT pendulum bounded to the angles where the lab interior is
// actually rendered, plus a 'focus' state that flies the camera in to
// the selected agent on click.
// ──────────────────────────────────────────────────────────────────────

/** World-space pivot the ambient pendulum orbits. Roughly the centre of action. */
const AMBIENT_TARGET = new THREE.Vector3(3.5, 1.4, -2.2);

/** Distance from pivot to camera when the pendulum is centred. */
const AMBIENT_RADIUS = 5.4;

/** Polar angle (zenith → camera). 0 = top-down, π/2 = horizontal. */
const AMBIENT_POLAR = Math.PI * 0.42;

/**
 * Centre azimuth of the pendulum. Three.js OrbitControls measures the
 * azimuthal angle from the +Z axis around the world Y axis, so 0 puts
 * the camera at +Z relative to the target — i.e. in front of the lab,
 * looking back along -Z toward the action zone where the GLB's front
 * face is open. The lab's "back" walls and unrendered exterior live to
 * the +X / -X / -Z sides, which we never want to drift into.
 */
const AMBIENT_AZIMUTH_CENTER = 0;

/** Half-amplitude of the pendulum (radians). 22° each side. */
const AMBIENT_AZIMUTH_RANGE = THREE.MathUtils.degToRad(22);

/** Full pendulum cycle in seconds — slow enough to feel ambient. */
const AMBIENT_PERIOD = 26;

/** Damp time (seconds) when re-acquiring the ambient pose after a focus. */
const AMBIENT_DAMP = 1.0;

// ── Focus mode (camera flies to a clicked agent) ──────────────────────

/** Horizontal distance from the agent the camera settles at. */
const FOCUS_OFFSET_DIST = 2.4;

/** Camera Y offset above the agent's foot position. */
const FOCUS_HEIGHT = 1.95;

/** Where the camera looks (Y above the agent's foot). */
const FOCUS_LOOKAT_HEIGHT = 1.55;

/** Damp time for the fly-in transition. */
const FOCUS_DAMP = 0.65;

/** Once the camera is within this distance of the focus target, hand control back to OrbitControls. */
const FOCUS_SETTLED_TOL = 0.08;

type OrbitLike = {
  target: THREE.Vector3;
  update: () => void;
  addEventListener: (event: string, cb: () => void) => void;
  removeEventListener: (event: string, cb: () => void) => void;
};

export function CameraDirector({
  controlsRef,
}: {
  controlsRef: MutableRefObject<unknown>;
}) {
  const { camera } = useThree();
  const { editMode } = useLayoutEdit();
  const { selectedSlotId } = useAgentLive();

  const slot = useMemo(
    () => SCIENTISTS.find((s) => s.id === selectedSlotId) ?? null,
    [selectedSlotId]
  );

  const ambientPhaseRef = useRef(0);
  const userInteractingRef = useRef(false);
  /**
   * Once the focus fly-in has converged, we yield to OrbitControls so the
   * user can orbit around the agent freely. Reset whenever the selected
   * slot changes (or is cleared) so a new click triggers a fresh fly-in.
   */
  const focusSettledRef = useRef(false);

  useEffect(() => {
    focusSettledRef.current = false;
  }, [selectedSlotId]);

  // Pause director writes whenever the user is dragging / zooming /
  // panning so OrbitControls' own state machine wins for that gesture.
  useEffect(() => {
    const ctrl = controlsRef.current as OrbitLike | null;
    if (!ctrl?.addEventListener) return;
    const onStart = () => {
      userInteractingRef.current = true;
    };
    const onEnd = () => {
      userInteractingRef.current = false;
    };
    ctrl.addEventListener("start", onStart);
    ctrl.addEventListener("end", onEnd);
    return () => {
      ctrl.removeEventListener("start", onStart);
      ctrl.removeEventListener("end", onEnd);
    };
  }, [controlsRef]);

  useFrame((_, dt) => {
    const ctrl = controlsRef.current as OrbitLike | null;
    if (!ctrl) return;
    if (editMode) return;
    if (userInteractingRef.current) return;

    // ── Focus on a selected agent ────────────────────────────────────
    if (slot) {
      if (focusSettledRef.current) return;

      const ax = slot.position[0];
      const ay = slot.position[1];
      const az = slot.position[2];

      // Place the camera on the line FROM the lab centre THROUGH the
      // agent, pushed FOCUS_OFFSET_DIST further out — that composition
      // looks at the agent from the same side they're already facing
      // when standing at their station, and keeps the camera inside
      // the rendered lab volume rather than pointing at the back wall.
      const dx = ax - AMBIENT_TARGET.x;
      const dz = az - AMBIENT_TARGET.z;
      const len = Math.max(Math.hypot(dx, dz), 0.1);
      const camX = ax + (dx / len) * FOCUS_OFFSET_DIST;
      const camZ = az + (dz / len) * FOCUS_OFFSET_DIST;
      const camY = ay + FOCUS_HEIGHT;
      const lookY = ay + FOCUS_LOOKAT_HEIGHT;

      const lambda = 1 / FOCUS_DAMP;
      camera.position.x = THREE.MathUtils.damp(camera.position.x, camX, lambda, dt);
      camera.position.y = THREE.MathUtils.damp(camera.position.y, camY, lambda, dt);
      camera.position.z = THREE.MathUtils.damp(camera.position.z, camZ, lambda, dt);
      ctrl.target.x = THREE.MathUtils.damp(ctrl.target.x, ax, lambda, dt);
      ctrl.target.y = THREE.MathUtils.damp(ctrl.target.y, lookY, lambda, dt);
      ctrl.target.z = THREE.MathUtils.damp(ctrl.target.z, az, lambda, dt);
      ctrl.update();

      const remaining = Math.hypot(
        camera.position.x - camX,
        camera.position.y - camY,
        camera.position.z - camZ
      );
      if (remaining < FOCUS_SETTLED_TOL) {
        focusSettledRef.current = true;
      }
      return;
    }

    // ── Ambient pendulum ─────────────────────────────────────────────
    ambientPhaseRef.current += dt;
    const phase = (ambientPhaseRef.current * 2 * Math.PI) / AMBIENT_PERIOD;
    const azimuth =
      AMBIENT_AZIMUTH_CENTER + AMBIENT_AZIMUTH_RANGE * Math.sin(phase);
    const sinPolar = Math.sin(AMBIENT_POLAR);
    const cosPolar = Math.cos(AMBIENT_POLAR);

    const camX = AMBIENT_TARGET.x + AMBIENT_RADIUS * sinPolar * Math.sin(azimuth);
    const camY = AMBIENT_TARGET.y + AMBIENT_RADIUS * cosPolar;
    const camZ = AMBIENT_TARGET.z + AMBIENT_RADIUS * sinPolar * Math.cos(azimuth);

    const lambda = 1 / AMBIENT_DAMP;
    camera.position.x = THREE.MathUtils.damp(camera.position.x, camX, lambda, dt);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, camY, lambda, dt);
    camera.position.z = THREE.MathUtils.damp(camera.position.z, camZ, lambda, dt);
    ctrl.target.x = THREE.MathUtils.damp(
      ctrl.target.x,
      AMBIENT_TARGET.x,
      lambda,
      dt
    );
    ctrl.target.y = THREE.MathUtils.damp(
      ctrl.target.y,
      AMBIENT_TARGET.y,
      lambda,
      dt
    );
    ctrl.target.z = THREE.MathUtils.damp(
      ctrl.target.z,
      AMBIENT_TARGET.z,
      lambda,
      dt
    );
    ctrl.update();
  });

  return null;
}
