export const LAB_GLB = "/3d-lab/sci-fi_lab.glb";

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
  // Bigger radius so the strolls cover real lab ground rather than
  // jittering next to the workstation. Per-slot override available.
  radius: 2.5,
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
export const SCIENTISTS: ScientistSlot[] = [
  {
    // Slot 1 ↔ 5 model swap: this slot now renders scientist-5's GLBs.
    id: "1",
    zone: "1 · floor right of GATE 07",
    url: "/3d-lab/scientist-5-walk.glb",
    idleUrl: "/3d-lab/scientist-5-idle.glb",
    position: [8.175426042597449, 0.02577319356117805, -4.3035778789495165],
    rotation: [-3.141592653589793, 1.4551804632888736, -3.141592653589793],
  },
  {
    // Slot 2 ↔ 3 model swap: this slot now renders scientist-3's GLBs.
    id: "2",
    zone: "2 · green workstation wall",
    url: "/3d-lab/scientist-3-walk.glb",
    idleUrl: "/3d-lab/scientist-3-idle.glb",
    position: [7.678855221765017, 0.06042707976589268, -1.0638662251660016],
    rotation: [-3.141592653589793, 1.4400210547869952, -3.141592653589793],
  },
  {
    // Slot 2 ↔ 3 model swap: this slot now renders scientist-2's GLBs.
    id: "3",
    zone: "3 · left blue tanks / pipes",
    url: "/3d-lab/scientist-2-walk.glb",
    idleUrl: "/3d-lab/scientist-2-idle.glb",
    position: [4.021386137837405, 0.056348486161091546, -1.5024284946462654],
    rotation: [3.119599245400525, 0.07009911961135065, -3.1330113468574026],
  },
  {
    id: "4",
    zone: "4 · center tile (table ↔ cylinder)",
    url: "/3d-lab/scientist-4-walk.glb",
    idleUrl: "/3d-lab/scientist-4-idle.glb",
    position: [-0.008629919775650807, 0.02692167797101399, -3.484664732923385],
    rotation: [3.141592653589793, -0.02806375087044089, 3.141592653589793],
  },
  {
    // Slot 1 ↔ 5 model swap: this slot now renders scientist-1's GLBs.
    // NOTE: Meshy swapped scientist-1's clip files — the "-walk" GLB
    // actually contains an idle clip ("Idle_13") and the "-idle" GLB
    // contains the walking clip ("Texting_Walk"). The URLs below cross
    // them so each clip lands in the right role.
    id: "5",
    zone: "5 · floor near specimen chamber",
    url: "/3d-lab/scientist-1-idle.glb",
    idleUrl: "/3d-lab/scientist-1-walk.glb",
    position: [0.19763748807533577, 0.05242026540169442, -0.501541107009971],
    rotation: [-3.141592653589793, 1.4905378342005715, -3.141592653589793],
  },
];

export const LAB_TARGET_FOOTPRINT = 12;

export const SCIENTIST_TARGET_HEIGHT = 1.78;
