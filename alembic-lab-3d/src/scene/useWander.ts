import { type RefObject, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { WANDER_DEFAULTS, type WanderTuning } from "./labSceneConfig";

export type WanderState = "IDLE" | "WALKING";

type Runtime = {
  state: WanderState;
  /** Absolute time (seconds) at which the IDLE phase ends. */
  idleUntil: number;
  /**
   * Queue of waypoints the agent will visit in order. Empty when IDLE.
   * The LAST element is always the anchor (0,0,0) — every tour ends with
   * a return-home leg, so IDLE only ever fires at the anchor.
   */
  targets: THREE.Vector3[];
  /** Current local position, written to the inner group each frame. */
  pos: THREE.Vector3;
  /** Current Y heading (radians) in LOCAL frame. */
  facingY: number;
  /** Heading the agent is currently turning toward. */
  desiredY: number;
};

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
 *  2. IDLE → WALKING when timer expires. The agent plans a short *tour*:
 *     1–2 random waypoints inside its wander radius, plus a final
 *     waypoint at the anchor (0,0,0). It walks them in order.
 *  3. On arrival at the anchor (last queue element) → IDLE again. IDLE
 *     therefore only happens at the home position; any wandering always
 *     ends with a return-home leg.
 *  4. Y-rotation is damped toward the velocity heading; on arrival home
 *     the heading drifts back toward the anchor's configured rotation
 *     (which is applied by the parent TransformableAgent).
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
        targets: [],
        pos: new THREE.Vector3(),
        facingY: 0,
        desiredY: 0,
      };
    }

    const r = rt.current;

    // IDLE → plan a tour: 1–2 intermediate waypoints + return-home leg.
    if (r.state === "IDLE" && now >= r.idleUntil) {
      const legCount = 1 + (Math.random() < 0.45 ? 1 : 0);
      for (let i = 0; i < legCount; i++) {
        const angle = Math.random() * Math.PI * 2;
        // Bias targets away from the dead-centre so the leg actually
        // covers a noticeable distance instead of jittering in place.
        const radius = (0.45 + 0.55 * Math.random()) * cfg.radius;
        r.targets.push(
          new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius)
        );
      }
      // Final waypoint is always the anchor — IDLE can only resume at home.
      r.targets.push(new THREE.Vector3(0, 0, 0));
      r.state = "WALKING";
      onStateRef.current?.("WALKING");
    }

    if (r.state === "WALKING" && r.targets.length > 0) {
      const tgt = r.targets[0]!;
      const dx = tgt.x - r.pos.x;
      const dz = tgt.z - r.pos.z;
      const dist = Math.hypot(dx, dz);

      if (dist < 0.04) {
        // Reached this waypoint — pop and either continue or settle home.
        r.targets.shift();
        if (r.targets.length === 0) {
          // Snap exactly to the anchor so position is bit-clean for IDLE.
          r.pos.set(0, 0, 0);
          r.state = "IDLE";
          r.idleUntil =
            now + cfg.idleMin + Math.random() * (cfg.idleMax - cfg.idleMin);
          // Drift heading back toward the anchor rotation (local Y = 0)
          // so the scientist faces "forward" again while idling.
          r.desiredY = 0;
          onStateRef.current?.("IDLE");
        }
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
  });
}
