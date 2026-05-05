import { type RefObject, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { WANDER_DEFAULTS, type WanderTuning } from "./labSceneConfig";

export type WanderState = "IDLE" | "WALKING";

type Runtime = {
  state: WanderState;
  /** Absolute time (seconds) at which the IDLE phase ends. */
  idleUntil: number;
  /** Target waypoint in LOCAL frame of the agent's anchor. */
  target: THREE.Vector3;
  /** Current local position, written to the inner group each frame. */
  pos: THREE.Vector3;
  /** Current Y heading (radians) in LOCAL frame. */
  facingY: number;
  /** Heading the agent is currently turning toward. */
  desiredY: number;
};

const _vec = new THREE.Vector3();

/** Wrap an angle delta into the (-π, π] range. */
function shortestAngularDelta(from: number, to: number): number {
  const TAU = Math.PI * 2;
  let d = (to - from) % TAU;
  if (d > Math.PI) d -= TAU;
  if (d < -Math.PI) d += TAU;
  return d;
}

/**
 * Periodic wandering for a scientist agent — runs entirely in the LOCAL
 * frame of its anchor (the parent ``TransformableAgent`` group), so the
 * configured anchor rotation in ``labSceneConfig`` is preserved as the
 * "facing forward" baseline and edit-mode gizmos keep working.
 *
 * Behaviour:
 *  1. Initial random idle (0..idleMax) so a fresh scene doesn't have all
 *     scientists step off in lockstep.
 *  2. IDLE → WALKING when timer expires; pick a random target inside a
 *     disc of radius ``cfg.radius`` around (0,0,0) in local frame.
 *  3. Step toward target at ``cfg.speed`` (m/s), damp Y-rotation toward
 *     the velocity heading.
 *  4. On arrival (within 4 cm) → IDLE again with a fresh random pause.
 *
 * Returns nothing; writes ``group.position`` and ``group.rotation``
 * imperatively each frame to avoid React reconcile churn.
 */
export function useWander(
  groupRef: RefObject<THREE.Group | null>,
  options: {
    enabled: boolean;
    tuning?: Partial<WanderTuning>;
    onState?: (next: WanderState) => void;
  }
) {
  const rt = useRef<Runtime | null>(null);
  const onStateRef = useRef(options.onState);
  onStateRef.current = options.onState;

  useFrame((_, dt) => {
    const group = groupRef.current;
    if (!group) return;

    if (!options.enabled) {
      group.position.set(0, 0, 0);
      group.rotation.set(0, 0, 0);
      rt.current = null;
      return;
    }

    const cfg: WanderTuning = { ...WANDER_DEFAULTS, ...(options.tuning ?? {}) };
    const now = performance.now() / 1000;

    if (!rt.current) {
      rt.current = {
        state: "IDLE",
        // Spread initial idle over the full idleMax window so the lab
        // doesn't look choreographed on first paint.
        idleUntil: now + Math.random() * cfg.idleMax,
        target: new THREE.Vector3(),
        pos: new THREE.Vector3(),
        facingY: 0,
        desiredY: 0,
      };
    }

    const r = rt.current;

    if (r.state === "IDLE" && now >= r.idleUntil) {
      const angle = Math.random() * Math.PI * 2;
      // Bias targets away from dead-centre so the agent actually moves
      // a noticeable distance instead of jittering in place.
      const radius = (0.45 + 0.55 * Math.random()) * cfg.radius;
      r.target.set(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
      r.state = "WALKING";
      onStateRef.current?.("WALKING");
    }

    if (r.state === "WALKING") {
      const dx = r.target.x - r.pos.x;
      const dz = r.target.z - r.pos.z;
      const dist = Math.hypot(dx, dz);

      if (dist < 0.04) {
        r.state = "IDLE";
        r.idleUntil =
          now + cfg.idleMin + Math.random() * (cfg.idleMax - cfg.idleMin);
        onStateRef.current?.("IDLE");
      } else {
        const step = Math.min(cfg.speed * dt, dist);
        r.pos.x += (dx / dist) * step;
        r.pos.z += (dz / dist) * step;
        // Local-frame +Z is "forward" for these models; atan2(dx, dz)
        // gives the Y rotation that aligns +Z with the velocity vector.
        r.desiredY = Math.atan2(dx, dz);
      }
    }

    // Damp the Y-rotation toward desiredY using the shortest arc, so the
    // agent never spins the long way around when the angle wraps past π.
    const turnLambda = 1 / Math.max(cfg.turnDamp, 1e-3);
    const delta = shortestAngularDelta(r.facingY, r.desiredY);
    r.facingY = THREE.MathUtils.damp(r.facingY, r.facingY + delta, turnLambda, dt);

    group.position.set(r.pos.x, r.pos.y, r.pos.z);
    // Anchor's rotation is already on the parent group — only modulate Y here.
    group.rotation.set(0, r.facingY, 0);

    // suppress unused-var lint on _vec; keeps the alloc out of the hot loop
    void _vec;
  });
}
