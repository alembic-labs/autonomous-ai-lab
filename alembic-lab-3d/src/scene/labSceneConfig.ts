export const LAB_GLB = "/3d-lab/sci-fi_lab.glb";

/**
 * Maps a 3D-lab slot to one of the five backend agent roles. The order
 * matches the AGENT_NAMES tuple in alembic-labs-backend's models.py so
 * that ``GET /api/agents/status`` can be looked up by role.
 */
export type AgentRole =
  | "RESEARCHER"
  | "LITERATURE"
  | "STRUCTURAL"
  | "CLINICAL"
  | "COMMUNICATOR";

export type WanderTuning = {
  /** Max radius (in world units, ≈meters) the agent strays from its anchor. */
  radius: number;
  /** Walking speed in units/sec. Comfortable indoor walk ≈ 0.5–0.7. */
  speed: number;
  /** Time constant for damped Y-rotation toward velocity heading (seconds). */
  turnDamp: number;
  /** Idle pause range between walks (seconds). */
  idleMin: number;
  idleMax: number;
};

export type ScientistSlot = {
  id: string;
  /** Backend agent role this slot represents. Drives the live-status hookup. */
  agentRole: AgentRole;
  /**
   * Primary GLB — supplies the rigged mesh + skeleton + walk-cycle clip.
   * Meshy's animation export packs the full character into every clip
   * file, so this file's mesh is what the agent renders and its single
   * animation is the agent's walk loop.
   */
  url: string;
  zone: string;
  /** Optional secondary GLB whose clip is grafted on as the IDLE animation. */
  idleUrl?: string;
  position: [number, number, number];
  rotation?: [number, number, number];
  /** Extra uniform scale after height fit (some GLBs under-report bbox vs skinned bounds). */
  scaleMultiplier?: number;
  /** Roam around the anchor when not in edit mode. Defaults to true. */
  wandering?: boolean;
  /** Per-slot tuning override. Defaults to WANDER_DEFAULTS. */
  wander?: Partial<WanderTuning>;
};

export const WANDER_DEFAULTS: WanderTuning = {
  // Conservative default — the lab interior is tight (~12u footprint with
  // furniture) and we have no navmesh to keep agents off the walls. The
  // wall-adjacent slots (1, 2, 3) override this to a smaller value below.
  radius: 1.4,
  speed: 0.55,
  turnDamp: 0.22,
  // Long home-pause: scientists should LOOK like they're working at their
  // station most of the time and only occasionally take a stroll. Combined
  // with the global single-walker lock (see useWander.ts), this gives the
  // lab a natural pace where one scientist strolls at a time.
  idleMin: 9.0,
  idleMax: 24.0,
};

/** Snapshots from downloaded lab-layout.json (manual placement in viewer). */
// Slot → backend agent role and model assignment. Positions are kept in
// sync with public/3d-lab/lab-layout.json (download from edit mode).
//
//   slot 1 (GATE 07, RESEARCHER)        → scientist-3
//   slot 2 (green workstation, LITERATURE) → scientist-5
//   slot 3 (left blue tanks, STRUCTURAL)   → scientist-1 (Meshy clip-file swap)
//   slot 4 (center tile, CLINICAL)         → scientist-4
//   slot 5 (chamber floor, COMMUNICATOR)   → scientist-2
export const SCIENTISTS: ScientistSlot[] = [
  {
    id: "1",
    agentRole: "RESEARCHER",
    zone: "1 · floor right of GATE 07",
    url: "/3d-lab/scientist-3-walk.glb",
    idleUrl: "/3d-lab/scientist-3-idle.glb",
    position: [7.840038856989182, 0.02577319356117805, -4.3035778789495165],
    rotation: [-3.141592653589793, 1.4551804632888736, -3.141592653589793],
    // Wall-adjacent slot — small radius keeps strolls off the wall.
    wander: { radius: 1.0 },
  },
  {
    id: "2",
    agentRole: "LITERATURE",
    zone: "2 · green workstation wall",
    url: "/3d-lab/scientist-5-walk.glb",
    idleUrl: "/3d-lab/scientist-5-idle.glb",
    position: [7.678855221765017, 0.06042707976589268, -1.0638662251660016],
    rotation: [-3.141592653589793, 0.369104816108874, -3.141592653589793],
    wander: { radius: 1.0 },
  },
  {
    // NOTE: Meshy swapped scientist-1's clip files — the "-walk" GLB
    // actually contains an idle clip ("Idle_13") and the "-idle" GLB
    // contains the walking clip ("Texting_Walk"). The URLs below cross
    // them so each clip lands in the right role.
    id: "3",
    agentRole: "STRUCTURAL",
    zone: "3 · left blue tanks / pipes",
    url: "/3d-lab/scientist-1-idle.glb",
    idleUrl: "/3d-lab/scientist-1-walk.glb",
    position: [3.9819030068548122, -0.03329913225105001, -1.4765850322723677],
    rotation: [3.1183503969865987, -0.33638788336252434, 3.1409602313454115],
    // User reported #3 wandering past the lab wall on the right; tight
    // radius keeps the strolls inside the central aisle.
    wander: { radius: 0.9 },
  },
  {
    id: "4",
    agentRole: "CLINICAL",
    zone: "4 · center tile (table ↔ cylinder)",
    url: "/3d-lab/scientist-4-walk.glb",
    idleUrl: "/3d-lab/scientist-4-idle.glb",
    position: [-0.008629919775650807, 0.02692167797101399, -3.484664732923385],
    rotation: [3.141592653589793, -0.02806375087044089, 3.141592653589793],
  },
  {
    id: "5",
    agentRole: "COMMUNICATOR",
    zone: "5 · floor near specimen chamber",
    url: "/3d-lab/scientist-2-walk.glb",
    idleUrl: "/3d-lab/scientist-2-idle.glb",
    position: [0.09661040177628033, 0.05242026540169442, -0.5082157680367915],
    rotation: [-3.141592653589793, 1.301001325303724, -3.141592653589793],
  },
];

export const LAB_TARGET_FOOTPRINT = 12;

export const SCIENTIST_TARGET_HEIGHT = 1.78;
