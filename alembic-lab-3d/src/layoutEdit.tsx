import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";
import { SCIENTISTS } from "./scene/labSceneConfig";

export type AgentTransform = {
  position: [number, number, number];
  rotation: [number, number, number];
};

function defaultTransforms(): Record<string, AgentTransform> {
  const o: Record<string, AgentTransform> = {};
  for (const s of SCIENTISTS) {
    o[s.id] = {
      position: [...s.position] as [number, number, number],
      rotation: [...(s.rotation ?? [0, 0, 0])] as [number, number, number],
    };
  }
  return o;
}

export type LayoutEditContextValue = {
  editMode: boolean;
  setEditMode: (v: boolean) => void;
  selectedId: string;
  setSelectedId: (id: string) => void;
  transforms: Record<string, AgentTransform>;
  syncFromObject: (
    id: string,
    pos: { x: number; y: number; z: number },
    rot: { x: number; y: number; z: number }
  ) => void;
  tcMode: "translate" | "rotate";
  setTcMode: (m: "translate" | "rotate") => void;
  orbitRef: MutableRefObject<unknown>;
  exportLayoutFile: () => void;
};

const LayoutEditContext = createContext<LayoutEditContextValue | null>(null);

export function LayoutEditProvider({ children }: { children: ReactNode }) {
  const orbitRef = useRef<unknown>(null);
  const [editMode, setEditMode] = useState(() => {
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("edit") === "1";
  });
  const [selectedId, setSelectedId] = useState("1");
  const [tcMode, setTcMode] = useState<"translate" | "rotate">("translate");
  const [transforms, setTransforms] = useState(defaultTransforms);

  const syncFromObject = useCallback(
    (
      id: string,
      pos: { x: number; y: number; z: number },
      rot: { x: number; y: number; z: number }
    ) => {
      setTransforms((prev) => ({
        ...prev,
        [id]: {
          position: [pos.x, pos.y, pos.z],
          rotation: [rot.x, rot.y, rot.z],
        },
      }));
    },
    []
  );

  const exportLayoutFile = useCallback(() => {
    const payload = {
      scientists: SCIENTISTS.map((s) => ({
        id: s.id,
        zone: s.zone,
        url: s.url,
        position: transforms[s.id].position,
        rotation: transforms[s.id].rotation,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "lab-layout.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }, [transforms]);

  const value = useMemo(
    () => ({
      editMode,
      setEditMode,
      selectedId,
      setSelectedId,
      transforms,
      syncFromObject,
      tcMode,
      setTcMode,
      orbitRef,
      exportLayoutFile,
    }),
    [
      editMode,
      selectedId,
      transforms,
      syncFromObject,
      tcMode,
      exportLayoutFile,
    ]
  );

  return (
    <LayoutEditContext.Provider value={value}>
      {children}
    </LayoutEditContext.Provider>
  );
}

export function useLayoutEdit(): LayoutEditContextValue {
  const v = useContext(LayoutEditContext);
  if (!v) throw new Error("useLayoutEdit: wrap App in LayoutEditProvider");
  return v;
}
