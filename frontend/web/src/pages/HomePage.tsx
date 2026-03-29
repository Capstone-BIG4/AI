import { Link } from "react-router-dom";

import { DEFAULT_OBJ_ASSET_PATH } from "../viewer/constants";

export function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">Step 0 Baseline</p>
        <h1>Capstone Virtual Fitting</h1>
        <p className="lead">
          Frontend scaffold for the upload, processing, garment selection, and
          result viewer flow.
        </p>
        <div className="status-grid">
          <div className="status-card">
            <h2>Web</h2>
            <p>React + Vite shell</p>
          </div>
          <div className="status-card">
            <h2>API</h2>
            <p>FastAPI skeleton</p>
          </div>
          <div className="status-card">
            <h2>Infra</h2>
            <p>Redis, MongoDB, MinIO compose</p>
          </div>
        </div>
        <div className="viewer-launch-panel">
          <div>
            <p className="eyebrow">Step 3 Output</p>
            <h2>OBJ Viewer Ready</h2>
            <p className="lead viewer-panel-copy">
              현재 smoke test 결과 OBJ를 브라우저에서 직접 회전해볼 수 있는 viewer route 추가 상태.
            </p>
            <code className="path-code">{DEFAULT_OBJ_ASSET_PATH}</code>
          </div>
          <div className="viewer-launch-actions">
            <Link
              className="primary-link-button"
              to={`/viewer/obj?asset=${encodeURIComponent(DEFAULT_OBJ_ASSET_PATH)}`}
            >
              Open Current Mesh
            </Link>
            <Link className="ghost-link-button" to="/viewer/obj">
              Open Viewer Shell
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
