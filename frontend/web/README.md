# Web App

React + Vite skeleton for Step 0.

Current scope:

- app bootstrap
- router shell
- query provider
- placeholder upload landing page
- Three.js OBJ viewer route

Viewer route:

- `/viewer/obj`
- query param: `asset=/absolute/path/to/raw_mesh.obj`

Runtime note:

- local filesystem OBJ loading uses Vite dev server `/@fs` path bridge
- default sample path can be set with `VITE_VIEWER_DEFAULT_OBJ_PATH`

Runtime prerequisite:

- Node.js 18.18 or newer
