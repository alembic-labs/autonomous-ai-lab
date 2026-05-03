import { useEffect, useRef, useState, type ReactNode } from "react";
import { TransformControls } from "@react-three/drei";
import * as THREE from "three";
import { useLayoutEdit } from "../layoutEdit";

export function TransformableAgent({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  const {
    editMode,
    selectedId,
    setSelectedId,
    transforms,
    syncFromObject,
    tcMode,
    orbitRef,
  } = useLayoutEdit();
  const t = transforms[id];
  const [grp, setGrp] = useState<THREE.Group | null>(null);
  const tcRef = useRef<unknown>(null);

  useEffect(() => {
    const tc = tcRef.current as {
      addEventListener: (
        ev: string,
        fn: (e: { value: boolean }) => void
      ) => void;
      removeEventListener: (
        ev: string,
        fn: (e: { value: boolean }) => void
      ) => void;
    } | null;
    const orbit = orbitRef.current as { enabled?: boolean } | null;
    if (!tc || !orbit) return;
    const onDrag = (e: { value: boolean }) => {
      orbit.enabled = !e.value;
    };
    tc.addEventListener("dragging-changed", onDrag);
    return () => {
      tc.removeEventListener("dragging-changed", onDrag);
    };
  }, [editMode, selectedId, orbitRef]);

  const showGizmo = editMode && selectedId === id;

  return (
    <>
      <group
        ref={setGrp}
        position={t.position}
        rotation={t.rotation}
        onClick={(e) => {
          if (!editMode) return;
          e.stopPropagation();
          setSelectedId(id);
        }}
        onPointerOver={
          editMode
            ? (e) => {
                e.stopPropagation();
                document.body.style.cursor = "pointer";
              }
            : undefined
        }
        onPointerOut={
          editMode
            ? () => {
                document.body.style.cursor = "";
              }
            : undefined
        }
      >
        {children}
      </group>
      {showGizmo && grp ? (
        <TransformControls
          ref={tcRef as never}
          object={grp}
          mode={tcMode}
          size={0.75}
          onObjectChange={() => {
            syncFromObject(id, grp.position, grp.rotation);
          }}
        />
      ) : null}
    </>
  );
}
