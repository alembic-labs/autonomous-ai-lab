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
  /** Static base GLB — provides the mesh + rest skeleton the agent renders. */
  url: string;
  zone: string;
  /** Walk-cycle GLB. Animation clips are pulled from here and retargeted onto ``url``'s skeleton. */
  walkUrl?: string;
  /** Idle GLB. Optional — without it the IDLE state falls back to the base rest pose. */
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
  radius: 1.0,
  speed: 0.55,
  turnDamp: 0.22,
  idleMin: 4.5,
  idleMax: 11.0,
};

/** Snapshots from downloaded lab-layout.json (manual placement in viewer). */
export const SCIENTISTS: ScientistSlot[] = [
  {
    id: "1",
    zone: "1 · floor right of GATE 07",
    url: "/3d-lab/scientist-1.glb",
    walkUrl: "/3d-lab/scientist-1-walk.glb",
    idleUrl: "/3d-lab/scientist-1-idle.glb",
    position: [8.175426042597449, 0.02577319356117805, -4.3035778789495165],
    rotation: [-3.141592653589793, 1.4551804632888736, -3.141592653589793],
  },
  {
    id: "2",
    zone: "2 · green workstation wall",
    url: "/3d-lab/scientist-2.glb",
    walkUrl: "/3d-lab/scientist-2-walk.glb",
    idleUrl: "/3d-lab/scientist-2-idle.glb",
    position: [7.678855221765017, 0.06042707976589268, -1.0638662251660016],
    rotation: [-3.141592653589793, 1.4400210547869952, -3.141592653589793],
  },
  {
    id: "3",
    zone: "3 · left blue tanks / pipes",
    url: "/3d-lab/scientist-3.glb",
    walkUrl: "/3d-lab/scientist-3-walk.glb",
    idleUrl: "/3d-lab/scientist-3-idle.glb",
    position: [4.021386137837405, 0.056348486161091546, -1.5024284946462654],
    rotation: [3.119599245400525, 0.07009911961135065, -3.1330113468574026],
  },
  {
    id: "4",
    zone: "4 · center tile (table ↔ cylinder)",
    url: "/3d-lab/scientist-4.glb",
    walkUrl: "/3d-lab/scientist-4-walk.glb",
    idleUrl: "/3d-lab/scientist-4-idle.glb",
    position: [-0.008629919775650807, 0.02692167797101399, -3.484664732923385],
    rotation: [3.141592653589793, -0.02806375087044089, 3.141592653589793],
  },
  {
    id: "5",
    zone: "5 · blue cylindrical chamber",
    url: "/3d-lab/scientist-5.glb",
    // No walk anim wired — wandering disabled below; idle plays continuously inside the chamber.
    idleUrl: "/3d-lab/scientist-5-idle.glb",
    position: [0.28362921116237416, 1.6461800946291325, -0.35922740080251647],
    rotation: [-3.141592653589793, 1.4905378342005715, -3.141592653589793],
    // scaleMultiplier was tuned for the previous bbox-misreporting GLB; the
    // new Meshy export sizes correctly via fitScientistUniformHeight alone.
    // Re-add a multiplier here only if #5 looks wrong inside the chamber.
    wandering: false,
  },
];

export const LAB_TARGET_FOOTPRINT = 12;

export const SCIENTIST_TARGET_HEIGHT = 1.78;
