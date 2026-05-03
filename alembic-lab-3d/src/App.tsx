import { LabCanvas } from "./LabCanvas";
import { LayoutEditProvider, useLayoutEdit } from "./layoutEdit";

const mainSite =
  import.meta.env.VITE_MAIN_SITE_URL || "https://alembic.bio";

function EditToolbar() {
  const {
    editMode,
    setEditMode,
    selectedId,
    setSelectedId,
    tcMode,
    setTcMode,
    exportLayoutFile,
  } = useLayoutEdit();

  return (
    <div className="edit-toolbar">
      <button
        type="button"
        className={`edit-btn ${editMode ? "edit-btn-on" : ""}`}
        onClick={() => setEditMode(!editMode)}
      >
        {editMode ? "готово" : "расставить людей"}
      </button>
      {editMode ? (
        <>
          <span className="edit-label">кто:</span>
          {(["1", "2", "3", "4", "5"] as const).map((n) => (
            <button
              key={n}
              type="button"
              className={`edit-chip ${selectedId === n ? "edit-chip-on" : ""}`}
              onClick={() => setSelectedId(n)}
            >
              {n}
            </button>
          ))}
          <span className="edit-label">ось:</span>
          <button
            type="button"
            className={`edit-chip ${tcMode === "translate" ? "edit-chip-on" : ""}`}
            onClick={() => setTcMode("translate")}
          >
            двигать
          </button>
          <button
            type="button"
            className={`edit-chip ${tcMode === "rotate" ? "edit-chip-on" : ""}`}
            onClick={() => setTcMode("rotate")}
          >
            крутить
          </button>
          <button type="button" className="edit-btn edit-btn-dl" onClick={exportLayoutFile}>
            скачать lab-layout.json
          </button>
          <span className="edit-hint">
            клик по человеку → цветные стрелки; колесо как обычно крутит камеру
          </span>
        </>
      ) : null}
    </div>
  );
}

function AppInner() {
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <span className="app-title">ALEMBIC LABS — 3d floor</span>
          <nav className="app-nav">
            <a href={mainSite}>main site</a>
            <span className="app-muted">drag · scroll zoom</span>
          </nav>
        </div>
        <EditToolbar />
      </header>
      <div className="app-canvas-wrap">
        <LabCanvas />
      </div>
    </>
  );
}

export function App() {
  return (
    <LayoutEditProvider>
      <AppInner />
    </LayoutEditProvider>
  );
}
