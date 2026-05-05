import { LabCanvas } from "./LabCanvas";
import { LayoutEditProvider, useLayoutEdit } from "./layoutEdit";
import { AgentLiveProvider } from "./agents/agentLive";
import { AgentInfoPanel } from "./agents/AgentInfoPanel";
import { LabPulseProvider } from "./agents/labPulse";
import { LabHUD } from "./agents/LabHUD";

const mainSite =
  import.meta.env.VITE_MAIN_SITE_URL || "https://alembic.bio";

/**
 * Layout-edit toolbar is an internal placement tool, not a public
 * feature. Gate the UI behind ``?edit=1`` so end users never see the
 * Cyrillic placement chrome but the dev workflow (drop scientists,
 * download lab-layout.json) keeps working.
 */
function isEditUiEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const sp = new URLSearchParams(window.location.search);
    return sp.get("edit") === "1";
  } catch {
    return false;
  }
}

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

function AppInner({ editUi }: { editUi: boolean }) {
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <span className="app-title">ALEMBIC LABS — 3d floor</span>
          <nav className="app-nav">
            <a href={mainSite}>main site</a>
            <span className="app-muted">click an agent · drag · scroll</span>
          </nav>
        </div>
        {editUi ? <EditToolbar /> : null}
      </header>
      <div className="app-canvas-wrap">
        <LabCanvas />
        <LabHUD />
        <AgentInfoPanel />
      </div>
    </>
  );
}

export function App() {
  const editUi = isEditUiEnabled();
  return (
    <LayoutEditProvider>
      <AgentLiveProvider>
        <LabPulseProvider>
          <AppInner editUi={editUi} />
        </LabPulseProvider>
      </AgentLiveProvider>
    </LayoutEditProvider>
  );
}
