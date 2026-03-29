import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ObjViewerCanvas } from "../viewer/ObjViewerCanvas";
import { DEFAULT_OBJ_ASSET_PATH, resolveObjAssetUrl } from "../viewer/constants";

type ViewerStatus = {
  phase: "idle" | "loading" | "ready" | "error";
  message: string;
};

type MeshStats = {
  vertices: number;
  faces: number;
};

export function ObjViewerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryAsset = searchParams.get("asset") || DEFAULT_OBJ_ASSET_PATH;

  const [assetInput, setAssetInput] = useState(queryAsset);
  const [resolvedAssetPath, setResolvedAssetPath] = useState(queryAsset);
  const [wireframe, setWireframe] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [darkStage, setDarkStage] = useState(false);
  const [cameraPreset, setCameraPreset] = useState<"front" | "angle" | "side" | "back">("angle");
  const [viewerStatus, setViewerStatus] = useState<ViewerStatus>({
    phase: "idle",
    message: "OBJ path 입력 대기",
  });
  const [meshStats, setMeshStats] = useState<MeshStats | null>(null);

  useEffect(() => {
    setAssetInput(queryAsset);
    setResolvedAssetPath(queryAsset);
  }, [queryAsset]);

  const resolvedAssetUrl = useMemo(
    () => resolveObjAssetUrl(resolvedAssetPath),
    [resolvedAssetPath],
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const nextValue = assetInput.trim();
    setResolvedAssetPath(nextValue);

    const nextParams = new URLSearchParams(searchParams);
    if (nextValue) {
      nextParams.set("asset", nextValue);
    } else {
      nextParams.delete("asset");
    }
    setSearchParams(nextParams, { replace: true });
  };

  const handleLoadDefault = () => {
    setAssetInput(DEFAULT_OBJ_ASSET_PATH);
    setResolvedAssetPath(DEFAULT_OBJ_ASSET_PATH);
    setSearchParams(
      new URLSearchParams({
        asset: DEFAULT_OBJ_ASSET_PATH,
      }),
      { replace: true },
    );
  };

  return (
    <main className="viewer-page-shell">
      <section className="viewer-sidebar">
        <div className="viewer-sidebar-card">
          <p className="eyebrow">OBJ Viewer</p>
          <h1>Step 3 Mesh Viewer</h1>
          <p className="lead">
            Step 3 reconstruction output OBJ를 Vite dev server의 <code>/@fs</code> 경로로 직접 로드하는
            최소 3D viewer.
          </p>
          <div className="viewer-actions-row">
            <Link className="primary-link-button" to="/">
              Home
            </Link>
            <button className="secondary-button" type="button" onClick={handleLoadDefault}>
              Load Current Sample
            </button>
          </div>
        </div>

        <div className="viewer-sidebar-card">
          <form className="viewer-form" onSubmit={handleSubmit}>
            <label className="field-label" htmlFor="asset-path">
              OBJ absolute path
            </label>
            <textarea
              id="asset-path"
              className="path-input"
              rows={4}
              value={assetInput}
              onChange={(event) => setAssetInput(event.target.value)}
              spellCheck={false}
            />
            <button className="primary-button" type="submit">
              Load Mesh
            </button>
          </form>
          <div className="info-stack">
            <div className="info-card">
              <span className="info-label">Resolved URL</span>
              <code className="path-code">{resolvedAssetUrl || "empty"}</code>
            </div>
            <div className="info-card">
              <span className="info-label">Status</span>
              <strong className={`status-pill status-${viewerStatus.phase}`}>{viewerStatus.phase}</strong>
              <p>{viewerStatus.message}</p>
            </div>
            <div className="info-card">
              <span className="info-label">Mesh Stats</span>
              <p>{meshStats ? `${meshStats.vertices.toLocaleString()} vertices` : "mesh 미로드 상태"}</p>
              <p>{meshStats ? `${meshStats.faces.toLocaleString()} faces` : "camera preset 변경 가능 상태"}</p>
            </div>
          </div>
        </div>

        <div className="viewer-sidebar-card">
          <div className="toolbar-section">
            <span className="info-label">Camera Preset</span>
            <div className="chip-row">
              <button
                className={cameraPreset === "angle" ? "chip-button chip-active" : "chip-button"}
                type="button"
                onClick={() => setCameraPreset("angle")}
              >
                Angle
              </button>
              <button
                className={cameraPreset === "front" ? "chip-button chip-active" : "chip-button"}
                type="button"
                onClick={() => setCameraPreset("front")}
              >
                Front
              </button>
              <button
                className={cameraPreset === "side" ? "chip-button chip-active" : "chip-button"}
                type="button"
                onClick={() => setCameraPreset("side")}
              >
                Side
              </button>
              <button
                className={cameraPreset === "back" ? "chip-button chip-active" : "chip-button"}
                type="button"
                onClick={() => setCameraPreset("back")}
              >
                Back
              </button>
            </div>
          </div>

          <div className="toggle-list">
            <label className="toggle-row">
              <input
                checked={wireframe}
                onChange={(event) => setWireframe(event.target.checked)}
                type="checkbox"
              />
              <span>Wireframe</span>
            </label>
            <label className="toggle-row">
              <input
                checked={autoRotate}
                onChange={(event) => setAutoRotate(event.target.checked)}
                type="checkbox"
              />
              <span>Auto Rotate</span>
            </label>
            <label className="toggle-row">
              <input
                checked={darkStage}
                onChange={(event) => setDarkStage(event.target.checked)}
                type="checkbox"
              />
              <span>Dark Stage</span>
            </label>
          </div>
        </div>

        <div className="viewer-sidebar-card">
          <span className="info-label">Current Artifact Set</span>
          <ul className="path-list">
            <li>
              <a href={resolvedAssetUrl} target="_blank" rel="noreferrer">
                Raw Mesh OBJ
              </a>
            </li>
          </ul>
        </div>
      </section>

      <section className="viewer-main-panel">
        <header className="viewer-main-header">
          <div>
            <p className="eyebrow">Three.js</p>
            <h2>Interactive OBJ Stage</h2>
          </div>
          <p className="viewer-help-text">drag orbit / wheel zoom / right drag pan</p>
        </header>
        <ObjViewerCanvas
          assetUrl={resolvedAssetUrl}
          autoRotate={autoRotate}
          cameraPreset={cameraPreset}
          darkStage={darkStage}
          onMeshStatsChange={setMeshStats}
          onStatusChange={setViewerStatus}
          wireframe={wireframe}
        />
      </section>
    </main>
  );
}
