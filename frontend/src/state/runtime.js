export const runtimeState = {
  running: false,
  complete: false,
  viewerOpen: false,
  viewerZoom: 1,
  runtimeTimer: null,
  pollTimer: null,
  runStartedAt: 0,
  uploadedFiles: new Map(),
  objectUrls: new Map()
};

export function formatRuntime(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}
